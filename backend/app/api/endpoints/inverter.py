"""
Inverter Agent API端点
提供数据逆变器功能
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.database import get_db
from app.db.models import ResearchTask, TaskStatus
from app.agents.inverter import InverterAgent
from app.core.llm_factory import configure_llm
from app.core.logging import logger

router = APIRouter()


class InverterRequest(BaseModel):
    """逆变器请求"""

    query: str = "数据逆变转换"
    config: dict = {}


class InverterResponse(BaseModel):
    """逆变器响应"""

    task_id: int
    message: str


@router.post("/inverter", response_model=InverterResponse)
async def run_inverter(
    request: InverterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    运行数据逆变器
    处理111.csv文件并进行数据转换
    """
    # 创建任务记录
    task = ResearchTask(
        query=request.query, config=request.config, status=TaskStatus.PENDING
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(f"创建逆变器任务: {task.id}")

    # 后台执行逆变器
    background_tasks.add_task(run_inverter_background, task.id, db)

    return InverterResponse(
        task_id=task.id, message="逆变器任务已启动，开始处理111.csv数据"
    )


async def run_inverter_background(task_id: int, db: AsyncSession):
    """
    后台执行逆变器任务
    """
    try:
        # 获取LLM配置
        llm_config = settings.get_llm_config()
        if not llm_config.get("api_key"):
            raise ValueError("未配置LLM API Key")

        # 配置LLM
        factory = configure_llm(
            provider=llm_config.get("provider", "openai"),
            api_key=llm_config["api_key"],
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model"),
        )

        # 创建逆变器agent
        inverter = InverterAgent(
            llm=factory.get_client(),
            model=factory.get_model(),
            llm_factory=factory,
        )

        # 准备上下文
        context = {
            "core_context": {
                "task_id": task_id,
                "query": "数据逆变转换",
                "research_plan": [],
                "current_phase": "inversion",
                "verified_facts": [],
                "key_entities": [],
                "constraints": [],
            },
            "extended_context": {
                "agent_type": "inverter",
                "working_data": {},
                "intermediate_results": [],
                "source_references": [],
                "notes": [],
            },
        }

        # 执行逆变器
        result = await inverter.execute(context)

        # 更新任务状态
        query = select(ResearchTask).filter(ResearchTask.id == task_id)
        task_result = await db.execute(query)
        task = task_result.scalar_one()

        if result.success:
            task.status = TaskStatus.COMPLETED
            task.progress = 100.0
            # 将转换结果保存到报告内容中
            import json

            task.report_content = json.dumps(
                result.output, ensure_ascii=False, indent=2
            )
            task.summary = (
                f"逆变器处理完成，转换了{result.output.get('original_rows', 0)}行数据"
            )
        else:
            task.status = TaskStatus.FAILED
            task.summary = f"逆变器处理失败: {', '.join(result.errors)}"

        await db.commit()

        logger.info(f"逆变器任务完成: {task_id}, 成功={result.success}")

    except Exception as e:
        logger.error(f"逆变器任务失败 {task_id}: {e}")

        # 更新任务状态为失败
        try:
            query = select(ResearchTask).filter(ResearchTask.id == task_id)
            task_result = await db.execute(query)
            task = task_result.scalar_one()
            task.status = TaskStatus.FAILED
            task.summary = f"逆变器处理异常: {str(e)}"
            await db.commit()
        except Exception as db_e:
            logger.error(f"更新任务状态失败: {db_e}")
