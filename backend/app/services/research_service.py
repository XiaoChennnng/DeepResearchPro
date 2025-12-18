"""
研究服务 - 核心业务逻辑
"""

import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from openai import AsyncOpenAI

from app.db.models import (
    ResearchTask,
    TaskStatus,
    PlanItem,
    Source,
    AgentLog,
    AgentType,
    KnowledgeNode as DBKnowledgeNode,
    ContextSnapshot,
    Chart,
)
from app.schemas.research import AgentStatusSchema
from app.core.logging import logger
from app.core.config import settings
from app.core.llm_factory import get_llm_factory, configure_llm, LLMFactory
from app.api.endpoints.websocket import get_ws_manager
from app.agents.workflow import ResearchWorkflow


class ResearchService:
    """
    研究服务类
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ws_manager = get_ws_manager()

        # 初始化LLM客户端（支持多模型提供商）
        self.llm_client, self.model, self.llm_factory = self._create_llm_client()

        # 初始化Agent实时状态存储
        self.agent_status = {}

        # 创建状态更新回调函数
        async def status_callback(status_update):
            agent_type = status_update["agent_type"]
            self.agent_status[agent_type] = status_update
            # 通过WebSocket广播状态更新
            asyncio.create_task(self._broadcast_agent_status(status_update))

        # 初始化工作流
        self.workflow = ResearchWorkflow(
            llm_client=self.llm_client,
            search_tools={"duckduckgo": True},  # 启用DuckDuckGo搜索
            model=self.model,
            llm_factory=self.llm_factory,
            status_callback=status_callback,
        )

    async def _broadcast_agent_status(self, status_update: Dict[str, Any]) -> None:
        """广播Agent状态更新到WebSocket客户端"""
        try:
            # 如果是子任务更新，发送agent_subtask_update消息
            if status_update.get("subtask_update"):
                subtask_message = {
                    "type": "agent_subtask_update",
                    "task_id": None,  # 会在前端处理时设置
                    "agent_type": status_update["agent_type"],
                    "api_calls": status_update["api_calls"],
                    "tokens_used": status_update["tokens_used"],
                    "duration": f"{status_update.get('duration_ms', 0) / 1000:.1f}s"
                    if status_update.get("duration_ms", 0) > 0
                    else "-",
                    "sub_task": {
                        "id": f"current_subtask_{status_update['agent_type']}",  # 使用固定ID，方便前端更新
                        "title": status_update["current_subtask"],
                        "status": "running",
                        "start_time": datetime.now().isoformat(),
                        "end_time": None,
                        "result": "",
                        "detail": status_update["current_subtask"],
                    },
                    "timestamp": datetime.now().isoformat(),
                }
                await self.ws_manager.broadcast_all(subtask_message)

            # 发送常规的状态更新
            duration_ms = status_update.get("duration_ms", 0)
            duration = f"{duration_ms / 1000:.1f}s" if duration_ms > 0 else "-"

            message = {
                "type": "agent_status_update",
                "agent_type": status_update["agent_type"],
                "api_calls": status_update["api_calls"],
                "tokens_used": status_update["tokens_used"],
                "duration": duration,
                "current_subtask": status_update["current_subtask"],
                "output_content": status_update["output_content"],
                "timestamp": datetime.now().isoformat(),
            }
            await self.ws_manager.broadcast_all(message)
        except Exception as e:
            logger.error(f"广播Agent状态失败: {e}")

    def _create_llm_client(self) -> tuple[Optional[AsyncOpenAI], str, Optional[Any]]:
        """
        创建LLM客户端
        """
        try:
            # 获取LLM配置
            llm_config = settings.get_llm_config()
            api_key = llm_config.get("api_key")
            provider = llm_config.get("provider", "openai")

            if not api_key or api_key == "your-api-key-here":
                logger.warning(
                    f"[ResearchService] LLM_API_KEY未配置，Agent无法运行"
                    f"当前提供商: {provider}"
                )
                return None, llm_config.get("model", "gpt-4o-mini"), None

            # 使用LLM工厂配置客户端
            factory = configure_llm(
                provider=provider,
                api_key=api_key,
                base_url=llm_config.get("base_url"),
                model=llm_config.get("model"),
            )

            client = factory.get_client()
            model = factory.get_model()

            logger.info(
                f"[ResearchService] LLM客户端初始化成功: "
                f"provider={provider}, model={model}"
            )
            return client, model, factory

        except Exception as e:
            logger.error(f"[ResearchService] LLM客户端初始化失败: {e}")
            return None, "gpt-4o-mini", None

    async def start_research(self, task_id: int):
        """
        启动研究任务
        """
        logger.info(f"[ResearchService] 开始研究任务: {task_id}")

        try:
            # 如果LLM客户端未正确初始化，直接将任务标记为失败并给出明确错误
            if not self.llm_client:
                logger.error(
                    "[ResearchService] LLM客户端未配置，无法执行研究任务，请先在环境变量或配置文件中设置 LLM_API_KEY/OPENAI_API_KEY"
                )

                task = await self._get_task(task_id)
                if task:
                    task.status = TaskStatus.FAILED
                    task.progress = 0.0
                    await self.db.commit()

                    # 记录一条初始化失败的Agent日志（归到规划阶段名下，方便前端展示）
                    await self._add_log(
                        task,
                        AgentType.PLANNER,
                        "初始化失败",
                        "研究任务启动失败：未配置大模型 API Key，系统无法调用真实LLM执行规划/搜索/分析/写作。请在后台正确配置 LLM_API_KEY 或 OPENAI_API_KEY 后重试。",
                        status="error",
                    )

                    # 通过WebSocket通知前端错误
                    await self.ws_manager.broadcast_to_task(
                        task_id,
                        {
                            "type": "error",
                            "task_id": task_id,
                            "message": "研究任务启动失败：未配置大模型 API Key，系统当前处于离线简化模式，已终止本次研究。",
                        },
                    )

                return

            # 获取任务
            task = await self._get_task(task_id)
            if not task:
                logger.error(f"[ResearchService] 任务不存在: {task_id}")
                return

            # 初始化为0%，进入规划阶段
            await self._update_task_status(task, TaskStatus.PLANNING, 0)

            # 定义进度回调
            async def progress_callback(status: str, progress: float):
                """进度回调，通知前端"""
                # 映射状态到TaskStatus
                status_map = {
                    "planning": TaskStatus.PLANNING,
                    "searching": TaskStatus.SEARCHING,
                    "curating": TaskStatus.CURATING,
                    "analyzing": TaskStatus.ANALYZING,
                    "writing": TaskStatus.WRITING,
                    "citing": TaskStatus.CITING,
                    "reviewing": TaskStatus.REVIEWING,
                    "completed": TaskStatus.COMPLETED,
                    "failed": TaskStatus.FAILED,
                }

                task_status = status_map.get(status, TaskStatus.PENDING)

                # 刷新任务对象
                refreshed_task = await self._get_task(task_id)
                if refreshed_task:
                    await self._update_task_status(
                        refreshed_task, task_status, progress
                    )

                    # 记录Agent阶段性执行日志
                    agent_type_map = {
                        "planning": AgentType.PLANNER,
                        "searching": AgentType.SEARCHER,
                        "curating": AgentType.CURATOR,
                        "analyzing": AgentType.ANALYZER,
                        "writing": AgentType.WRITER,
                        "citing": AgentType.CITER,
                        "reviewing": AgentType.REVIEWER,
                    }

                    # 使用更具体的操作描述，而不是笼统的"执行中"
                    current_action_map = {
                        "planning": "正在分析研究需求，制定详细的执行计划",
                        "searching": "正在执行多渠道信息搜索，收集相关数据",
                        "curating": "正在评估信息质量，筛选高质量来源",
                        "analyzing": "正在深度分析数据，发现关键洞察和趋势",
                        "writing": "正在组织内容结构，撰写专业报告",
                        "citing": "正在验证引用准确性，完善参考文献",
                        "reviewing": "正在审核报告完整性和事实准确性",
                    }

                    agent_label_map = {
                        AgentType.PLANNER: "规划Agent",
                        AgentType.SEARCHER: "搜索Agent",
                        AgentType.CURATOR: "筛选Agent",
                        AgentType.ANALYZER: "分析Agent",
                        AgentType.WRITER: "写作Agent",
                        AgentType.CITER: "引用Agent",
                        AgentType.REVIEWER: "审核Agent",
                    }

                    if status in agent_type_map:
                        agent_type = agent_type_map[status]
                        label = agent_label_map.get(agent_type, agent_type.value)
                        current_action = current_action_map.get(
                            status, f"{label}正在执行任务"
                        )

                        # 移除整体进度显示，只显示具体操作
                        await self._add_log(
                            refreshed_task,
                            agent_type,
                            "执行中",
                            current_action,
                        )

                        # 通过WebSocket推送Agent阶段活动状态
                        # 直接使用实时状态数据，避免metrics被重置
                        real_time_status = self.agent_status.get(agent_type.value, {})
                        duration_ms = real_time_status.get("duration_ms", 0)
                        duration = (
                            f"{duration_ms / 1000:.1f}s" if duration_ms > 0 else "-"
                        )
                        metrics = {
                            "tokensUsed": real_time_status.get("tokens_used", 0),
                            "apiCalls": real_time_status.get("api_calls", 0),
                            "duration": duration,
                        }

                        # 将整体进度映射为当前Agent阶段内的局部进度（0-100）
                        agent_progress = self._calculate_agent_progress(
                            progress, task_status
                        )

                        await self.ws_manager.broadcast_to_task(
                            task_id,
                            {
                                "type": "agent_activity",
                                "task_id": task_id,
                                "agent_type": agent_type.value,
                                "status": "active",
                                "current_task": current_action,
                                "progress": agent_progress,
                                "metrics": metrics,
                                "timestamp": datetime.utcnow().isoformat(),
                            },
                        )

            # 检查是否暂停
            task = await self._get_task(task_id)
            if not task:
                logger.error(f"[ResearchService] 任务不存在: {task_id}")
                return

            if task.status == TaskStatus.PAUSED:
                logger.info(f"[ResearchService] 任务 {task_id} 已暂停")
                return

            # 执行7 Agent工作流
            result = await self.workflow.run(
                task_id=task_id, query=task.query, callback=progress_callback
            )

            # 处理结果
            await self._process_workflow_result(task_id, result)

            logger.info(f"[ResearchService] 研究任务完成: {task_id}")

        except Exception as e:
            logger.error(f"[ResearchService] 研究任务失败: {task_id}, 错误: {e}")
            task = await self._get_task(task_id)
            if task:
                task.status = TaskStatus.FAILED
                await self.db.commit()

            # 通知前端
            await self.ws_manager.broadcast_to_task(
                task_id,
                {
                    "type": "error",
                    "task_id": task_id,
                    "message": f"研究任务失败: {str(e)}",
                },
            )

    async def _process_workflow_result(self, task_id: int, result: Dict[str, Any]):
        """
        处理工作流结果
        小陈说：把Agent的执行结果保存到数据库
        """
        task = await self._get_task(task_id)
        if not task:
            logger.error(f"[ResearchService] 处理结果时任务不存在: {task_id}")
            return

        # 从协调器状态中取出上下文，方便做回退逻辑
        orchestrator_state = result.get("orchestrator_state", {}) or {}
        core_context = orchestrator_state.get("core_context", {}) or {}
        extended_contexts = orchestrator_state.get("extended_contexts", {}) or {}

        # 统一计算最终报告内容
        # 1）优先使用Reviewer给出的final_report（通过审核的版本）
        # 2）如果审核未通过但已有带引用的报告，则回退到Citer阶段的report
        # 3）再不行则回退到Writer阶段的原始report，确保永远有一份可读报告
        final_report = result.get("final_report") or ""
        if not final_report:
            citer_ctx = extended_contexts.get("citer", {}) or {}
            writer_ctx = extended_contexts.get("writer", {}) or {}

            citer_working = citer_ctx.get("working_data", {}) or {}
            writer_working = writer_ctx.get("working_data", {}) or {}

            final_report = (
                citer_working.get("report") or writer_working.get("report") or ""
            )

            # 把回退得到的报告也写回result，方便后续指标统计与日志复用
            if final_report:
                result["final_report"] = final_report

        # 保存报告内容
        if final_report:
            task.report_content = final_report
            task.summary = (
                final_report[:500] + "..." if len(final_report) > 500 else final_report
            )

        # 保存来源
        for source_data in result.get("sources", []):
            await self._add_source(
                task,
                title=source_data.get("title", "未知来源"),
                url=source_data.get("url", ""),
                content=source_data.get("content", ""),
                confidence=source_data.get("confidence", "medium"),
                relevance_score=source_data.get("relevance_score", 0.5),
                is_curated=source_data.get("is_curated", False),
            )

        # 保存研究计划
        research_plan = core_context.get("research_plan", [])

        for i, step in enumerate(research_plan):
            if isinstance(step, dict):
                await self._add_plan_item(
                    task,
                    title=step.get("title", f"步骤 {i + 1}"),
                    description=step.get("description", ""),
                    order=i + 1,
                )

        # 保存知识图谱节点
        kg_data = orchestrator_state.get("knowledge_graph", {})
        for node_id, node_data in kg_data.get("nodes", {}).items():
            db_node = DBKnowledgeNode(
                task_id=task_id,
                node_type=node_data.get("node_type", "fact"),
                content=node_data.get("content", ""),
                source_ids=node_data.get("source_ids", []),
                created_by_agent=AgentType(
                    node_data.get("created_by_agent", "planner")
                ),
                is_verified=node_data.get("verification_status") == "verified",
                confidence_score=node_data.get("confidence_score", 0.5),
                verification_count=node_data.get("verification_count", 0),
                version=node_data.get("version", 1),
                related_node_ids=node_data.get("related_node_ids", []),
            )
            self.db.add(db_node)

        # 保存图表数据
        writer_result = result.get("agent_results", {}).get("writer", {})
        writer_output = writer_result.get("output", {})
        charts_data = writer_output.get("charts", [])

        for chart_data in charts_data:
            chart = Chart(
                task_id=task_id,
                chart_type=chart_data.get("chart_type", "bar"),
                title=chart_data.get("title", "未命名图表"),
                description=chart_data.get("description"),
                data=chart_data.get("data", {}),
                config=chart_data.get("config"),
                section=chart_data.get("section", "其他"),
                order=chart_data.get("order", 0),
                created_by_agent=AgentType.WRITER,
            )
            self.db.add(chart)

        # 保存上下文快照
        snapshot = ContextSnapshot(
            task_id=task_id,
            snapshot_type="final",
            core_context=core_context,
            extended_context=orchestrator_state.get("extended_contexts", {}),
            total_tokens=result.get("metrics", {}).get("total_tokens", 0),
        )
        self.db.add(snapshot)

        # 更新任务状态
        if result.get("status") == "completed":
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
        elif result.get("status") == "failed":
            task.status = TaskStatus.FAILED

        # 更新配置中的指标
        task.config = task.config or {}
        task.config["metrics"] = result.get("metrics", {})
        task.config["agent_results"] = result.get("agent_results", {})

        await self.db.commit()

        # 记录7个Agent的阶段性总结日志
        await self._log_agent_summaries(task, result)

        # 推送每个Agent的最终活动状态，便于前端展示协作结果
        agent_results: Dict[str, Any] = result.get("agent_results", {}) or {}
        if agent_results:
            for agent_name, info in agent_results.items():
                tokens_used = int(info.get("tokens_used", 0) or 0)
                duration_ms = int(info.get("duration_ms", 0) or 0)
                success = bool(info.get("success", True))

                status = "completed" if success else "failed"

                metrics = {
                    "tokensUsed": tokens_used,
                    "apiCalls": 0,
                    "duration_ms": duration_ms,
                }

                await self.ws_manager.broadcast_to_task(
                    task_id,
                    {
                        "type": "agent_activity",
                        "task_id": task_id,
                        "agent_type": agent_name,
                        "status": status,
                        "current_task": "阶段执行完成",
                        "progress": 100 if success else task.progress,
                        "metrics": metrics,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

        # 通知前端刷新数据（特别是筛选后的数据）
        await self.ws_manager.broadcast_to_task(
            task_id,
            {
                "type": "data_refresh",
                "task_id": task_id,
                "message": "数据已更新，请刷新显示",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        # 通知前端完成
        await self.ws_manager.broadcast_to_task(
            task_id,
            {
                "type": "completed",
                "task_id": task_id,
                "result": {
                    "status": result.get("status"),
                    "report_length": len(result.get("final_report", "")),
                    "sources_count": len(result.get("sources", [])),
                    "metrics": result.get("metrics", {}),
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def resume_research(self, task_id: int):
        """
        继续暂停的研究任务
        小陈说：继续干活，别偷懒
        """
        logger.info(f"[ResearchService] 继续研究任务: {task_id}")
        # 简化处理，重新从头开始
        # 实际应用中应该根据progress恢复到合适的阶段
        await self.start_research(task_id)

    async def get_agent_status(self, task_id: int) -> List[AgentStatusSchema]:
        """
        获取所有7个Agent的当前状态
        前端用这个接口展示Agent卡片
        """
        task = await self._get_task(task_id)
        if not task:
            return []

        # 7个Agent配置
        agent_configs = [
            (AgentType.PLANNER, TaskStatus.PLANNING, "研究计划制定"),
            (AgentType.SEARCHER, TaskStatus.SEARCHING, "信息收集"),
            (AgentType.CURATOR, TaskStatus.CURATING, "信息筛选"),
            (AgentType.ANALYZER, TaskStatus.ANALYZING, "数据分析"),
            (AgentType.WRITER, TaskStatus.WRITING, "报告撰写"),
            (AgentType.CITER, TaskStatus.CITING, "引用管理"),
            (AgentType.REVIEWER, TaskStatus.REVIEWING, "质量审核"),
        ]

        agents = []
        for agent_type, stage_status, task_name in agent_configs:
            status = self._determine_agent_status(task, stage_status, agent_type)

            # 获取Agent的指标
            metrics = await self._get_agent_metrics(task, agent_type)

            # 获取实时状态信息
            real_time_status = self.agent_status.get(agent_type.value, {})
            current_subtask = real_time_status.get("current_subtask", "")
            output_content = real_time_status.get("output_content", "")

            # 构建当前任务描述
            if status == "active" and current_subtask:
                current_task = current_subtask
            elif status == "active":
                current_task = f"{task_name}中"
            elif status == "completed":
                current_task = f"{task_name}完成"
            else:
                current_task = "等待中"

            agents.append(
                AgentStatusSchema(
                    agent_type=agent_type,
                    status=status,
                    current_task=current_task,
                    progress=self._calculate_agent_progress(
                        task.progress, stage_status
                    ),
                    metrics=metrics,
                    sub_tasks=[current_subtask] if current_subtask else [],
                    output_content=output_content,
                )
            )

        return agents

    async def _log_agent_summaries(
        self, task: ResearchTask, result: Dict[str, Any]
    ) -> None:
        """根据工作流结果为7个Agent记录一条阶段性总结日志"""
        agent_results: Dict[str, Any] = result.get("agent_results", {})
        if not agent_results:
            return

        sources = result.get("sources", []) or []
        orchestrator_state = result.get("orchestrator_state", {}) or {}
        core_context = orchestrator_state.get("core_context", {}) or {}
        research_plan = core_context.get("research_plan", []) or []
        kg_data = orchestrator_state.get("knowledge_graph", {}) or {}
        kg_nodes: Dict[str, Any] = kg_data.get("nodes", {}) or {}

        agent_meta = {
            "planner": (AgentType.PLANNER, "规划Agent"),
            "searcher": (AgentType.SEARCHER, "搜索Agent"),
            "curator": (AgentType.CURATOR, "筛选Agent"),
            "analyzer": (AgentType.ANALYZER, "分析Agent"),
            "writer": (AgentType.WRITER, "写作Agent"),
            "citer": (AgentType.CITER, "引用Agent"),
            "reviewer": (AgentType.REVIEWER, "审核Agent"),
        }

        for agent_name, info in agent_results.items():
            meta = agent_meta.get(agent_name)
            if not meta:
                continue

            agent_type, label = meta
            tokens_used = int(info.get("tokens_used", 0) or 0)
            duration_ms = int(info.get("duration_ms", 0) or 0)
            errors: List[str] = info.get("errors") or []
            success = bool(info.get("success", True)) and not errors

            details: List[str] = []

            if agent_name == "planner":
                steps_count = len(research_plan)
                details.append(f"生成 {steps_count} 个研究计划步骤")
            elif agent_name == "searcher":
                total_sources = len(sources)
                details.append(f"收集 {total_sources} 个候选信息来源")
            elif agent_name == "curator":
                curated_count = sum(1 for s in sources if s.get("is_curated"))
                details.append(f"筛选出 {curated_count} 个高质量来源")
            elif agent_name == "analyzer":
                analyzer_nodes = [
                    node
                    for node in kg_nodes.values()
                    if node.get("created_by_agent") == "analyzer"
                ]
                if analyzer_nodes:
                    details.append(f"生成 {len(analyzer_nodes)} 个分析结论节点")
            elif agent_name == "writer":
                report = result.get("final_report") or ""
                if report:
                    details.append(f"生成报告约 {len(report)} 字")
            elif agent_name == "citer":
                citer_nodes = [
                    node
                    for node in kg_nodes.values()
                    if node.get("created_by_agent") == "citer"
                ]
                if citer_nodes:
                    details.append(f"为报告添加 {len(citer_nodes)} 条引用/知识节点")
            elif agent_name == "reviewer":
                review_score = result.get("review_score")
                if review_score is not None:
                    details.append(f"审核得分 {review_score}")

            if errors:
                details.append("错误: " + "; ".join(errors))

            if not details:
                details.append("执行完成")

            duration_sec = duration_ms / 1000.0 if duration_ms > 0 else 0.0
            content = (
                f"{label}："
                + "；".join(details)
                + f"（tokens={tokens_used}, 耗时={duration_sec:.1f}s）"
            )

            await self._add_log(
                task,
                agent_type,
                "阶段总结",
                content,
                status="success" if success else "error",
                tokens_used=tokens_used,
                duration_ms=duration_ms,
            )

            # 更新当前子任务状态为完成
            current_subtask_id = f"current_subtask_{agent_name}"
            subtask_status = "completed" if success else "failed"

            await self.ws_manager.broadcast_to_task(
                task.id,
                {
                    "type": "agent_subtask_update",
                    "task_id": task.id,
                    "agent_type": agent_name,
                    "sub_task": {
                        "id": current_subtask_id,
                        "title": f"{label}阶段总结",
                        "status": subtask_status,
                        "start_time": None,
                        "end_time": datetime.utcnow().isoformat(),
                        "result": content,
                        "detail": "；".join(details),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

    async def _get_agent_metrics(
        self, task: ResearchTask, agent_type: AgentType
    ) -> Dict[str, Any]:
        """获取Agent的执行指标"""
        # 优先使用实时状态数据
        if agent_type.value in self.agent_status:
            status = self.agent_status[agent_type.value]
            duration = "-"
            # 注意：start_time属性不存在，这里暂时使用默认值

            return {
                "tokensUsed": status.get("tokens_used", 0),
                "apiCalls": status.get("api_calls", 0),
                "duration": duration,
            }

        # 回退到任务配置中的静态数据
        metrics = {"tokensUsed": 0, "apiCalls": 0, "duration": "-"}
        if task.config and "agent_results" in task.config:
            agent_result = task.config["agent_results"].get(agent_type.value, {})
            metrics["tokensUsed"] = agent_result.get("tokens_used", 0)
            duration_ms = agent_result.get("duration_ms", 0)
            if duration_ms > 0:
                metrics["duration"] = f"{duration_ms / 1000:.1f}s"

        return metrics

    def _determine_agent_status(
        self, task: ResearchTask, agent_stage: TaskStatus, agent_type: AgentType
    ) -> str:
        """根据任务状态确定Agent状态"""
        # 状态顺序（7个Agent）
        stage_order = {
            TaskStatus.PENDING: 0,
            TaskStatus.PLANNING: 1,
            TaskStatus.SEARCHING: 2,
            TaskStatus.CURATING: 3,
            TaskStatus.ANALYZING: 4,
            TaskStatus.WRITING: 5,
            TaskStatus.CITING: 6,
            TaskStatus.REVIEWING: 7,
            TaskStatus.COMPLETED: 8,
        }

        current_order = stage_order.get(task.status, 0)
        agent_order = stage_order.get(agent_stage, 0)

        if current_order > agent_order:
            return "completed"
        elif current_order == agent_order:
            return "active"
        else:
            return "idle"

    def _calculate_agent_progress(
        self, overall_progress: float, agent_stage: TaskStatus
    ) -> float:
        ranges = {
            TaskStatus.PLANNING: (0.0, 10.0),
            TaskStatus.SEARCHING: (10.0, 25.0),
            TaskStatus.CURATING: (25.0, 40.0),
            TaskStatus.ANALYZING: (40.0, 55.0),
            TaskStatus.WRITING: (55.0, 70.0),
            TaskStatus.CITING: (70.0, 85.0),
            TaskStatus.REVIEWING: (85.0, 95.0),
        }

        if overall_progress is None:
            return 0.0

        p = float(overall_progress)
        if p < 0.0:
            p = 0.0
        if p > 100.0:
            p = 100.0

        span = ranges.get(agent_stage)
        if not span:
            return p

        start, end = span
        if p <= start:
            return 0.0
        if p >= end:
            return 100.0

        return (p - start) / (end - start) * 100.0

    async def _get_task(self, task_id: int) -> Optional[ResearchTask]:
        """获取任务"""
        query = select(ResearchTask).filter(ResearchTask.id == task_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _update_task_status(
        self, task: ResearchTask, status: TaskStatus, progress: float
    ):
        """更新任务状态并通知前端"""
        task.status = status
        task.progress = progress
        await self.db.commit()

        # WebSocket通知
        await self.ws_manager.broadcast_to_task(
            task.id,
            {
                "type": "progress",
                "task_id": task.id,
                "progress": progress,
                "stage": status.value,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _add_log(
        self,
        task: ResearchTask,
        agent_type: AgentType,
        action: str,
        content: str,
        status: str = "info",
        tokens_used: int = 0,
        duration_ms: int = 0,
    ):
        """添加Agent日志并通知前端"""
        log = AgentLog(
            task_id=task.id,
            agent_type=agent_type,
            action=action,
            content=content,
            status=status,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )
        self.db.add(log)
        await self.db.commit()

        # WebSocket通知
        await self.ws_manager.broadcast_to_task(
            task.id,
            {
                "type": "agent_log",
                "task_id": task.id,
                "agent_type": agent_type.value,
                "action": action,
                "content": content,
                "status": status,
                "tokens_used": tokens_used,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def _add_plan_item(
        self,
        task: ResearchTask,
        title: str,
        description: str = "",
        parent_id: Optional[int] = None,
        order: int = 0,
    ):
        """添加计划项"""
        plan_item = PlanItem(
            task_id=task.id,
            parent_id=parent_id,
            title=title,
            description=description,
            status="pending",
            order=order,
        )
        self.db.add(plan_item)
        await self.db.commit()
        await self.db.refresh(plan_item)

        # WebSocket通知
        await self.ws_manager.broadcast_to_task(
            task.id,
            {
                "type": "plan_update",
                "task_id": task.id,
                "plan_item_id": plan_item.id,
                "title": title,
                "description": description,
                "status": "pending",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

        return plan_item

    async def _add_source(
        self,
        task: ResearchTask,
        title: str,
        url: str,
        content: str,
        confidence: str = "medium",
        relevance_score: float = 0.5,
        is_curated: bool = False,
    ):
        """添加信息来源"""
        source = Source(
            task_id=task.id,
            title=title,
            url=url,
            content=content,
            confidence=confidence,
            relevance_score=relevance_score,
            is_curated=is_curated,
            source_type="web",
        )
        self.db.add(source)
        await self.db.commit()

        # WebSocket通知
        await self.ws_manager.broadcast_to_task(
            task.id,
            {
                "type": "source_added",
                "task_id": task.id,
                "source": {
                    "title": title,
                    "url": url,
                    "content": content[:200] if content else "",
                    "confidence": confidence,
                    "relevance_score": relevance_score,
                    "is_curated": is_curated,
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
