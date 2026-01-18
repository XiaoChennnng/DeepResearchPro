"""
研究任务API端点
提供研究任务的创建、查询和管理接口
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.llm_factory import configure_llm
from app.db.database import get_db
from app.db.models import ResearchTask, TaskStatus, PlanItem, Source, AgentLog, Chart
from app.schemas.research import (
    ResearchTaskCreate,
    ResearchTaskUpdate,
    ResearchTaskResponse,
    ResearchTaskDetailResponse,
    ResearchTaskListResponse,
    AgentActivityResponse,
)
from app.services.research_service import ResearchService
from app.core.logging import logger
from app.api.deps import get_current_user

router = APIRouter()


class ReportQAHistoryItem(BaseModel):
    role: str
    content: str


class ReportQARequest(BaseModel):
    question: str
    history: list[ReportQAHistoryItem] | None = None


class ReportQAResponse(BaseModel):
    answer: str


class TitleResponse(BaseModel):
    title: str


@router.post("/tasks", response_model=ResearchTaskResponse)
async def create_research_task(
    task_data: ResearchTaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    创建新的研究任务
    小陈说：提交研究问题，后台自动开始干活
    """
    # 创建任务记录
    task = ResearchTask(
        query=task_data.query, config=task_data.config, status=TaskStatus.PENDING
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(f"创建研究任务: {task.id} - {task.query[:50]}...")

    # 后台启动研究流程
    research_service = ResearchService(db)
    background_tasks.add_task(research_service.start_research, task.id)

    return task


@router.get("/tasks", response_model=ResearchTaskListResponse)
async def list_research_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[TaskStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    获取研究任务列表
    支持分页和状态过滤
    """
    try:
        # 构建查询 - 只查询需要的列，避免加载relationship字段
        query = select(
            ResearchTask.id,
            ResearchTask.query,
            ResearchTask.status,
            ResearchTask.progress,
            ResearchTask.config,
            ResearchTask.report_content,
            ResearchTask.summary,
            ResearchTask.created_at,
            ResearchTask.updated_at,
            ResearchTask.completed_at,
        ).order_by(ResearchTask.created_at.desc())

        if status:
            query = query.filter(ResearchTask.status == status)

        # 获取总数
        count_query = select(func.count()).select_from(ResearchTask)
        if status:
            count_query = count_query.filter(ResearchTask.status == status)
        total = await db.scalar(count_query)

        query = query.offset(skip).limit(limit)
        result = await db.execute(query)
        rows = result.all()

        tasks = []
        for row in rows:
            # 1. 处理 Status - 极其健壮的容错处理
            status_raw = row[2]
            status_value = TaskStatus.PENDING

            if status_raw is not None:
                if isinstance(status_raw, TaskStatus):
                    status_value = status_raw
                else:
                    try:
                        status_value = TaskStatus(str(status_raw))
                    except ValueError:
                        logger.warning(
                            f"任务 {row[0]} 的状态值异常: {status_raw}，已重置为 PENDING"
                        )
                        status_value = TaskStatus.PENDING

            # 2. 处理 Progress
            progress_value = row[3] if row[3] is not None else 0.0

            # 3. 处理时间 - 防止 None 导致 Pydantic 报错
            from datetime import datetime

            created_at = row[7] if row[7] is not None else datetime.now()
            updated_at = row[8] if row[8] is not None else datetime.now()

            tasks.append(
                ResearchTaskResponse(
                    id=row[0],
                    query=row[1] or "",
                    status=status_value,
                    progress=float(progress_value),
                    config=row[4],
                    report_content=row[5],
                    summary=row[6],
                    created_at=created_at,
                    updated_at=updated_at,
                    completed_at=row[9],
                )
            )

        logger.info(
            f"[list_research_tasks] 查询成功，总数={total}, 返回={len(tasks)}条"
        )

        return ResearchTaskListResponse(total=total or 0, items=tasks)
    except Exception as e:
        logger.error(f"[list_research_tasks] 错误: {e}")
        import traceback

        traceback.print_exc()
        raise


@router.get("/tasks/{task_id}", response_model=ResearchTaskDetailResponse)
async def get_research_task(
    task_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    获取研究任务详情
    包括计划树、来源列表、最近日志
    """
    # 加载关联数据
    query = (
        select(ResearchTask)
        .options(
            selectinload(ResearchTask.plan_items),
            selectinload(ResearchTask.sources),
            selectinload(ResearchTask.agent_logs),
            selectinload(ResearchTask.charts),
        )
        .filter(ResearchTask.id == task_id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=404, detail="研究任务不存在，你是不是传错ID了？"
        )

    # 只返回最近的日志
    recent_logs = sorted(task.agent_logs, key=lambda x: x.created_at, reverse=True)[:50]

    return {
        "id": task.id,
        "query": task.query,
        "status": task.status,
        "progress": task.progress,
        "config": task.config,
        "report_content": task.report_content,
        "summary": task.summary,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "completed_at": task.completed_at,
        "plan_items": task.plan_items,
        "sources": task.sources,
        "recent_logs": recent_logs,
        "charts": task.charts,
    }


@router.patch("/tasks/{task_id}", response_model=ResearchTaskResponse)
async def update_research_task(
    task_id: int, 
    update_data: ResearchTaskUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    更新研究任务状态
    主要用于暂停/继续任务
    """
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 更新字段
    if update_data.status is not None:
        task.status = update_data.status
    if update_data.progress is not None:
        task.progress = update_data.progress

    await db.commit()
    await db.refresh(task)

    logger.info(f"更新任务 {task_id}: status={task.status}, progress={task.progress}")

    return task


@router.delete("/tasks/{task_id}")
async def delete_research_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """
    删除研究任务
    小陈提醒：删了就没了，别后悔
    """
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    await db.delete(task)
    await db.commit()

    logger.info(f"删除任务: {task_id}")

    return {"message": "任务已删除", "task_id": task_id}


@router.post("/tasks/{task_id}/pause")
async def pause_research_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """暂停研究任务"""
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
        raise HTTPException(status_code=400, detail="任务已结束，无法暂停")

    task.status = TaskStatus.PAUSED
    await db.commit()

    return {"message": "任务已暂停", "task_id": task_id}


@router.post("/tasks/{task_id}/resume")
async def resume_research_task(
    task_id: int, 
    background_tasks: BackgroundTasks, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """继续研究任务"""
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status != TaskStatus.PAUSED:
        raise HTTPException(status_code=400, detail="只能继续已暂停的任务")

    # 恢复任务状态
    task.status = TaskStatus.PLANNING  # 根据进度恢复到合适状态
    await db.commit()

    # 后台继续执行
    research_service = ResearchService(db)
    background_tasks.add_task(research_service.resume_research, task.id)

    return {"message": "任务已继续", "task_id": task_id}


@router.get("/tasks/{task_id}/agents", response_model=AgentActivityResponse)
async def get_agent_activity(task_id: int, db: AsyncSession = Depends(get_db)):
    """
    获取Agent活动状态
    前端用这个接口轮询或者初始化Agent状态
    """
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 从ResearchService获取Agent状态
    research_service = ResearchService(db)
    agents = await research_service.get_agent_status(task_id)

    return AgentActivityResponse(
        task_id=task_id, agents=agents, overall_progress=task.progress
    )


@router.post("/tasks/{task_id}/qa", response_model=ReportQAResponse)
async def ask_report_question(
    task_id: int, 
    payload: ReportQARequest, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = (
        select(ResearchTask)
        .options(selectinload(ResearchTask.sources))
        .filter(ResearchTask.id == task_id)
    )
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="研究任务不存在")

    report_content = (task.report_content or "").strip()
    if not report_content:
        raise HTTPException(status_code=400, detail="报告尚未生成，无法追问")

    question = (payload.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    llm_config = settings.get_llm_config()
    api_key = llm_config.get("api_key")
    provider = llm_config.get("provider", "openai")

    if not api_key or api_key == "your-api-key-here":
        raise HTTPException(
            status_code=400, detail="未配置LLM API Key，请先在账户页保存API配置"
        )

    try:
        factory = configure_llm(
            provider=provider,
            api_key=api_key,
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model"),
        )
        client = factory.get_client()
        model = factory.get_model()

        max_report_chars = 24000
        report_context = (
            report_content
            if len(report_content) <= max_report_chars
            else report_content[:max_report_chars] + "\n\n[报告内容已截断]"
        )

        sources = task.sources or []
        sources_preview = []
        for idx, src in enumerate(sources[:20], start=1):
            title = (src.title or "").strip()
            url = (src.url or "").strip()
            if url:
                sources_preview.append(f"[{idx}] {title} ({url})")
            else:
                sources_preview.append(f"[{idx}] {title}")

        system_prompt = (
            "你是DeepResearch Pro的报告问答助手。\n"
            "你必须仅基于【报告内容】回答用户问题；如果报告中没有足够信息，明确说明不确定，并给出如何补充信息的建议。\n"
            "输出要求：中文、结构清晰、尽量引用报告中的要点，不要编造数据。"
        )

        messages: list[dict] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "system",
                "content": "【报告内容】\n" + report_context,
            },
        ]

        if sources_preview:
            messages.append(
                {
                    "role": "system",
                    "content": "【参考来源列表】\n" + "\n".join(sources_preview),
                }
            )

        history = payload.history or []
        for item in history[-8:]:
            role = (item.role or "").strip().lower()
            if role not in {"user", "assistant"}:
                continue
            content = (item.content or "").strip()
            if not content:
                continue
            messages.append({"role": role, "content": content[:2000]})

        messages.append({"role": "user", "content": question})

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
        )

        answer = (resp.choices[0].message.content or "").strip()
        if not answer:
            raise ValueError("LLM返回空回答")

        return ReportQAResponse(answer=answer)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"报告追问失败 task_id={task_id}: {e}")
        raise HTTPException(status_code=500, detail="生成回答失败，请稍后重试")


@router.get("/tasks/{task_id}/title", response_model=TitleResponse)
async def generate_task_title(
    task_id: int, 
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = select(ResearchTask).filter(ResearchTask.id == task_id)
    result = await db.execute(query)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="研究任务不存在")

    research_query = (task.query or "").strip()
    if not research_query:
        raise HTTPException(status_code=400, detail="任务缺少研究问题，无法生成标题")

    llm_config = settings.get_llm_config()
    api_key = llm_config.get("api_key")
    provider = llm_config.get("provider", "openai")

    if not api_key or api_key == "your-api-key-here":
        task.status = TaskStatus.FAILED
        await db.commit()
        raise HTTPException(
            status_code=400, detail="未配置LLM API Key，无法生成研究标题，任务已标记为失败"
        )

    prompt = f"""你是一个资深学术期刊编辑，擅长为研究报告撰写简洁、专业的中文标题。

请根据下面的研究需求，总结一个合适的标题。

【研究需求】
{research_query}

【标题要求】
1. 使用中文。
2. 控制在20个汉字以内，尽量简洁。
3. 概括研究核心主题，避免空泛表达，如“关于……的研究”。
4. 不要包含引号、编号或多余说明。

只输出标题本身。
"""

    try:
        factory = configure_llm(
            provider=provider,
            api_key=api_key,
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model"),
        )
        client = factory.get_client()
        model = factory.get_model()

        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=64,
        )

        content = (resp.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("LLM返回空标题")

        title = content.strip().strip("\"").strip("'")
        if len(title) > 30:
            title = title[:30]

        if len(title) < 2:
            raise ValueError("生成的标题过短")

        return TitleResponse(title=title)
    except Exception as e:
        logger.error(f"生成研究标题失败 task_id={task_id}: {e}")
        task.status = TaskStatus.FAILED
        await db.commit()
        raise HTTPException(status_code=500, detail="生成研究标题失败，任务已标记为失败")
