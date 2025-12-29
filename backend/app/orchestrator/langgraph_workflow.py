"""LangGraph工作流引擎"""

from typing import Dict, Any, List, Optional, Callable, Awaitable, TypedDict
from datetime import datetime
from enum import Enum
import asyncio

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.base import AgentState
from app.orchestrator.context_orchestrator import (
    ContextOrchestrator,
    AgentExecutionResult,
)
from app.core.logging import logger


class WorkflowState(TypedDict):
    """LangGraph工作流状态"""

    task_id: int
    query: str
    orchestrator: ContextOrchestrator
    current_agent: str
    agent_results: Dict[str, AgentExecutionResult]
    retry_count: int
    max_retries: int
    errors: List[str]
    progress: float
    status: str
    start_time: datetime
    end_time: Optional[datetime]


class AgentPhase(str, Enum):
    """Agent执行阶段枚举"""

    PLANNER = "planner"
    SEARCHER = "searcher"
    CURATOR = "curator"
    ANALYZER = "analyzer"
    WRITER = "writer"
    CITER = "citer"
    REVIEWER = "reviewer"


class LangGraphWorkflow:
    """
    基于LangGraph的高级工作流引擎
    支持条件分支、并行执行、循环和错误恢复
    """

    def __init__(
        self,
        llm_client=None,
        search_tools: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback: Optional[Callable] = None,
    ):
        self.llm_client = llm_client
        self.search_tools = search_tools or {}
        self.model = model
        self.llm_factory = llm_factory
        self.status_callback = status_callback

        # 延迟初始化Agent，避免循环导入
        self._agents = None

        # Agent执行顺序和进度映射
        self.agent_sequence = [
            ("planner", "planning", 10),
            ("searcher", "searching", 25),
            ("curator", "curating", 40),
            ("analyzer", "analyzing", 55),
            ("writer", "writing", 70),
            ("citer", "citing", 85),
            ("reviewer", "reviewing", 95),
        ]

        # 构建LangGraph工作流
        self.graph = self._build_workflow_graph()

        logger.info("[LangGraphWorkflow] 高级工作流引擎初始化完成")

    @property
    def agents(self):
        """动态初始化Agent"""
        if self._agents is None:
            # 动态导入避免循环依赖
            from app.agents.planner import PlannerAgent
            from app.agents.searcher import SearcherAgent
            from app.agents.curator import CuratorAgent
            from app.agents.analyzer import AnalyzerAgent
            from app.agents.writer import WriterAgent
            from app.agents.citer import CiterAgent
            from app.agents.reviewer import ReviewerAgent

            self._agents = {
                "planner": PlannerAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "searcher": SearcherAgent(
                    search_tools=self.search_tools,
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "curator": CuratorAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "analyzer": AnalyzerAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "writer": WriterAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "citer": CiterAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
                "reviewer": ReviewerAgent(
                    llm=self.llm_client,
                    model=self.model,
                    llm_factory=self.llm_factory,
                    status_callback=self.status_callback,
                ),
            }
        return self._agents

    def _build_workflow_graph(self) -> StateGraph:
        """构建LangGraph工作流图"""

        # 定义工作流图
        workflow = StateGraph(WorkflowState)

        # 添加节点（每个Agent一个节点）
        for agent_name, agent in self.agents.items():
            workflow.add_node(agent_name, self._create_agent_node(agent_name, agent))

        # 添加条件边和路由逻辑
        workflow.set_entry_point("planner")

        # 主流程边
        workflow.add_edge("planner", "searcher")
        workflow.add_edge("searcher", "curator")
        workflow.add_edge("curator", "analyzer")
        workflow.add_edge("analyzer", "writer")

        # 审核通过的条件边
        workflow.add_conditional_edges(
            "reviewer",
            self._review_decision,
            {
                "completed": END,
                "revise": "writer",
                "failed": END,
            },
        )

        # Writer到Citer的边（正常流程）
        workflow.add_edge("writer", "citer")
        workflow.add_edge("citer", "reviewer")

        # 添加检查点支持
        checkpointer = MemorySaver()

        return workflow.compile(checkpointer=checkpointer)

    def _create_agent_node(self, agent_name: str, agent):
        """创建Agent节点函数"""

        async def agent_node(state: WorkflowState) -> WorkflowState:
            """Agent执行节点"""
            try:
                logger.info(f"[LangGraphWorkflow] 执行Agent: {agent_name}")

                # 更新当前Agent
                state["current_agent"] = agent_name

                # 获取对应的进度信息
                progress_info = next(
                    (
                        (status, None, progress)
                        for name, status, progress in self.agent_sequence
                        if name == agent_name
                    ),
                    (None, None, 0),
                )
                status_name, _, progress_value = progress_info

                # 发送进度更新
                if self.status_callback:
                    await self.status_callback(status_name, progress_value)

                # 获取上下文
                context = await state["orchestrator"].align_context_for_agent(
                    agent_name
                )

                # 执行Agent
                result = await agent.execute(context)

                # 同步结果到协调器
                await state["orchestrator"].sync_context_after_agent(agent_name, result)

                # 记录结果
                state["agent_results"][agent_name] = result

                # 检查执行结果
                if not result.success and result.errors:
                    logger.warning(
                        f"[LangGraphWorkflow] Agent {agent_name} 执行失败: {result.errors}"
                    )
                    state["errors"].extend(result.errors)

                    # 对于关键Agent失败，标记为失败状态
                    if agent_name in ["planner", "searcher"]:
                        state["status"] = "failed"
                        return state

                # 更新进度
                state["progress"] = progress_value

                return state

            except Exception as e:
                logger.error(
                    f"[LangGraphWorkflow] Agent {agent_name} 节点执行异常: {e}"
                )
                state["errors"].append(f"Agent {agent_name} 执行异常: {str(e)}")
                state["status"] = "failed"
                return state

        return agent_node

    def _review_decision(self, state: WorkflowState) -> str:
        """
        审核决策逻辑
        决定是完成、修改还是失败
        """
        reviewer_result = state["agent_results"].get("reviewer")
        if not reviewer_result or not reviewer_result.success:
            logger.warning("[LangGraphWorkflow] 审核Agent执行失败")
            return "failed"

        # 获取审核结果
        output = reviewer_result.output
        review_passed = output.get("passed", False)
        review_score = output.get("score", 0)
        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", 3)

        logger.info(
            f"[LangGraphWorkflow] 审核结果: 通过={review_passed}, "
            f"分数={review_score}, 重试次数={retry_count}/{max_retries}"
        )

        if review_passed:
            # 审核通过，流程完成
            state["status"] = "completed"
            state["end_time"] = datetime.utcnow()
            return "completed"
        elif retry_count < max_retries:
            # 审核未通过，但还有重试机会
            state["retry_count"] = retry_count + 1
            logger.info(
                f"[LangGraphWorkflow] 审核未通过，准备第{retry_count + 1}轮修改"
            )
            return "revise"
        else:
            # 达到最大重试次数，流程失败
            logger.warning(
                f"[LangGraphWorkflow] 达到最大重试次数{retry_count}，流程失败"
            )
            state["status"] = "failed"
            state["end_time"] = datetime.utcnow()
            return "failed"

    async def run(
        self,
        task_id: int,
        query: str,
        callback: Optional[Callable[[str, float], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        执行LangGraph工作流

        Args:
            task_id: 任务ID
            query: 研究问题
            callback: 进度回调函数

        Returns:
            工作流执行结果
        """

        logger.info(f"[LangGraphWorkflow] 开始执行高级工作流: task_id={task_id}")

        # 初始化上下文协调器
        orchestrator = ContextOrchestrator(
            task_id=task_id, query=query, llm_client=self.llm_client
        )

        if callback:
            orchestrator.set_progress_callback(callback)

        # 初始化工作流状态
        initial_state: WorkflowState = {
            "task_id": task_id,
            "query": query,
            "orchestrator": orchestrator,
            "current_agent": "",
            "agent_results": {},
            "retry_count": 0,
            "max_retries": 3,
            "errors": [],
            "progress": 0.0,
            "status": "running",
            "start_time": datetime.utcnow(),
            "end_time": None,
        }

        try:
            # 执行工作流
            config = {"configurable": {"thread_id": str(task_id)}}
            final_state = await self.graph.ainvoke(initial_state, config)

            # 构建返回结果
            result = {
                "task_id": task_id,
                "query": query,
                "status": final_state["status"],
                "progress": final_state["progress"],
                "errors": final_state["errors"],
                "agent_results": final_state["agent_results"],
                "retry_count": final_state["retry_count"],
                "start_time": final_state["start_time"].isoformat(),
                "end_time": final_state.get("end_time").isoformat()
                if final_state.get("end_time")
                else None,
            }

            # 从协调器提取最终结果
            if final_state["status"] == "completed":
                # 提取最终报告
                working_data = orchestrator.context_manager.extended_context.get(
                    "working_data", {}
                )
                result["final_report"] = working_data.get("final_report", "")

                # 提取审核分数
                review_result = final_state["agent_results"].get("reviewer", {})
                if review_result and review_result.success:
                    result["review_score"] = review_result.output.get("score", 0)

            # 收集指标
            result["metrics"] = self._collect_metrics(final_state)

            logger.info(
                f"[LangGraphWorkflow] 高级工作流完成: task_id={task_id}, "
                f"status={final_state['status']}, retries={final_state['retry_count']}"
            )

            return result

        except Exception as e:
            logger.error(f"[LangGraphWorkflow] 工作流执行异常: {e}")

            # 异常情况下返回失败结果
            return {
                "task_id": task_id,
                "query": query,
                "status": "failed",
                "progress": 0.0,
                "errors": [f"工作流执行异常: {str(e)}"],
                "agent_results": {},
                "retry_count": 0,
                "start_time": initial_state["start_time"].isoformat(),
                "end_time": datetime.utcnow().isoformat(),
                "metrics": {},
            }

    def _collect_metrics(self, state: WorkflowState) -> Dict[str, Any]:
        """收集工作流执行指标"""
        metrics = {
            "total_agents": len(state["agent_results"]),
            "successful_agents": sum(
                1 for r in state["agent_results"].values() if r.success
            ),
            "failed_agents": sum(
                1 for r in state["agent_results"].values() if not r.success
            ),
            "retry_count": state["retry_count"],
            "total_tokens": sum(r.tokens_used for r in state["agent_results"].values()),
            "total_duration_ms": sum(
                r.duration_ms for r in state["agent_results"].values()
            ),
        }

        # 计算执行时间
        if state.get("start_time") and state.get("end_time"):
            execution_time = (state["end_time"] - state["start_time"]).total_seconds()
            metrics["execution_time_seconds"] = execution_time

        return metrics

    def set_llm_client(self, client, model: str = "gpt-4o-mini", llm_factory=None):
        """设置LLM客户端"""
        self.llm_client = client
        self.model = model
        if llm_factory:
            self.llm_factory = llm_factory
        for agent in self.agents.values():
            agent.set_llm_client(client, model, llm_factory)
        logger.info("[LangGraphWorkflow] LLM客户端已更新")

    def set_search_tools(self, tools: Dict[str, Any]):
        """设置搜索工具"""
        self.search_tools = tools
        self.agents["searcher"].set_search_tools(tools)
        logger.info("[LangGraphWorkflow] 搜索工具已更新")
