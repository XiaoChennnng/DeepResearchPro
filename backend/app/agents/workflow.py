"""
研究工作流 - 7 Agent 协同
小陈说：这是多Agent协调的核心，整合中央协调器和7个Agent
全部对接真实LLM，没有任何模拟数据！
"""

from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime

from openai import AsyncOpenAI

from app.agents.base import AgentState
from app.agents.planner import PlannerAgent
from app.agents.searcher import SearcherAgent
from app.agents.curator import CuratorAgent
from app.agents.analyzer import AnalyzerAgent
from app.agents.writer import WriterAgent
from app.agents.citer import CiterAgent
from app.agents.reviewer import ReviewerAgent
from app.orchestrator.context_orchestrator import (
    ContextOrchestrator,
    AgentExecutionResult,
)
from app.core.logging import logger


class ResearchWorkflow:
    """
    研究工作流（7 Agent版本）
    小陈说：这是整个系统的核心，编排7个Agent协同工作

    Agent执行顺序：
    1. Planner - 规划研究任务
    2. Searcher - 搜索信息
    3. Curator - 筛选和整理信息
    4. Analyzer - 深度分析
    5. Writer - 撰写报告
    6. Citer - 添加引用
    7. Reviewer - 质量审核
    """

    # Agent执行阶段和进度映射
    AGENT_PHASES = [
        ("planner", "planning", 10),
        ("searcher", "searching", 25),
        ("curator", "curating", 40),
        ("analyzer", "analyzing", 55),
        ("writer", "writing", 70),
        ("citer", "citing", 85),
        ("reviewer", "reviewing", 95),
    ]

    def __init__(
        self,
        llm_client: Optional[AsyncOpenAI] = None,
        search_tools: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        llm_factory: Optional[Any] = None,
        status_callback: Optional[Callable] = None,
    ):
        self.llm_client = llm_client
        self.search_tools = search_tools or {}
        self.model = model
        self.llm_factory = llm_factory
        self.status_callback = status_callback

        # 初始化7个Agent
        self.agents = {
            "planner": PlannerAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "searcher": SearcherAgent(
                search_tools=search_tools,
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "curator": CuratorAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "analyzer": AnalyzerAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "writer": WriterAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "citer": CiterAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
            "reviewer": ReviewerAgent(
                llm=llm_client,
                model=model,
                llm_factory=llm_factory,
                status_callback=status_callback,
            ),
        }

        logger.info("[ResearchWorkflow] 初始化完成，7个Agent就位")

    def set_llm_client(
        self,
        client: AsyncOpenAI,
        model: str = "gpt-4o-mini",
        llm_factory: Optional[Any] = None,
    ) -> None:
        """设置LLM客户端"""
        self.llm_client = client
        self.model = model
        if llm_factory:
            self.llm_factory = llm_factory
        for agent in self.agents.values():
            agent.set_llm_client(client, model, llm_factory)
        logger.info("[ResearchWorkflow] LLM客户端已更新")

    def set_search_tools(self, tools: Dict[str, Any]) -> None:
        """设置搜索工具"""
        self.search_tools = tools
        self.agents["searcher"].set_search_tools(tools)
        logger.info("[ResearchWorkflow] 搜索工具已更新")

    async def run(
        self,
        task_id: int,
        query: str,
        callback: Optional[Callable[[str, float], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        执行完整的研究工作流

        Args:
            task_id: 任务ID
            query: 研究问题
            callback: 可选的回调函数，用于报告进度 (status, progress)

        Returns:
            包含最终结果的字典
        """
        logger.info(
            f"[ResearchWorkflow] 开始执行工作流: task_id={task_id}, query={query[:50]}..."
        )

        # 初始化中央协调器
        orchestrator = ContextOrchestrator(
            task_id=task_id, query=query, llm_client=self.llm_client
        )

        if callback:
            orchestrator.set_progress_callback(callback)

        # 存储执行结果
        results = {
            "task_id": task_id,
            "query": query,
            "status": "running",
            "errors": [],
            "agent_results": {},
            "final_report": "",
            "sources": [],
            "metrics": {},
        }

        try:
            # 依次执行7个Agent
            prev_progress = 0.0
            for agent_name, status, phase_end in self.AGENT_PHASES:
                logger.info(f"[ResearchWorkflow] 执行Agent: {agent_name}")

                # 阶段开始：用上一个阶段结束值作为起点进度，方便前端从0%开始渲染当前Agent进度
                if callback:
                    await callback(status, prev_progress)

                # 获取对齐后的上下文
                context = await orchestrator.align_context_for_agent(agent_name)

                # 执行Agent
                agent = self.agents[agent_name]
                result = await agent.execute(context)

                # 阶段结束：报告该阶段的目标进度，用于整体进度条和Agent局部进度收尾到100%
                if callback:
                    await callback(status, phase_end)

                # 更新上一阶段结束进度
                prev_progress = phase_end

                # 同步结果到协调器
                await orchestrator.sync_context_after_agent(agent_name, result)

                # 记录结果
                results["agent_results"][agent_name] = {
                    "success": result.success,
                    "tokens_used": result.tokens_used,
                    "duration_ms": result.duration_ms,
                    "errors": result.errors,
                }

                # 检查是否有严重错误
                if not result.success and result.errors:
                    logger.error(
                        f"[ResearchWorkflow] Agent {agent_name} 执行失败: {result.errors}"
                    )
                    # 非关键Agent失败不中断流程
                    if agent_name in ["planner", "searcher"]:
                        results["errors"].extend(result.errors)
                        results["status"] = "failed"
                        break

                # 收集中间结果
                if agent_name == "searcher":
                    results["sources"] = result.output.get("sources", [])
                elif agent_name == "reviewer":
                    results["final_report"] = result.output.get("final_report", "")
                    results["review_score"] = result.output.get("score", 0)

            if results.get("status") != "failed":
                rewrite_count = 0
                max_rewrites = 3
                while rewrite_count < max_rewrites:
                    core_ctx = orchestrator.context_manager.core_context
                    review_feedback = getattr(core_ctx, "review_feedback", {}) or {}

                    if not review_feedback or review_feedback.get("passed"):
                        break

                    logger.info(
                        "[ResearchWorkflow] 审核未通过，启动自动重写流程：Writer -> Citer -> Reviewer"
                    )

                    rewrite_stages = [
                        ("writer", "writing", 80.0),
                        ("citer", "citing", 88.0),
                        ("reviewer", "reviewing", 95.0),
                    ]

                    for agent_name, status, progress in rewrite_stages:
                        logger.info(
                            f"[ResearchWorkflow] 自动重写阶段执行Agent: {agent_name}"
                        )

                        if callback:
                            await callback(status, progress)

                        context = await orchestrator.align_context_for_agent(agent_name)
                        agent = self.agents[agent_name]
                        result = await agent.execute(context)

                        await orchestrator.sync_context_after_agent(agent_name, result)

                        prev = results["agent_results"].get(
                            agent_name,
                            {
                                "success": True,
                                "tokens_used": 0,
                                "duration_ms": 0,
                                "errors": [],
                            },
                        )

                        merged_errors = list(prev.get("errors", [])) + list(
                            result.errors or []
                        )
                        merged_tokens = int(prev.get("tokens_used", 0)) + int(
                            result.tokens_used or 0
                        )
                        merged_duration = int(prev.get("duration_ms", 0)) + int(
                            result.duration_ms or 0
                        )

                        merged_success = (
                            bool(prev.get("success", True))
                            and bool(result.success)
                            and not merged_errors
                        )

                        results["agent_results"][agent_name] = {
                            "success": merged_success,
                            "tokens_used": merged_tokens,
                            "duration_ms": merged_duration,
                            "errors": merged_errors,
                        }

                        if agent_name == "reviewer":
                            results["final_report"] = result.output.get(
                                "final_report", ""
                            )
                            results["review_score"] = result.output.get("score", 0)

                    core_ctx = orchestrator.context_manager.core_context
                    review_feedback = getattr(core_ctx, "review_feedback", {}) or {}
                    if review_feedback.get("passed"):
                        logger.info("[ResearchWorkflow] 自动重写后审核通过")
                        break

                    rewrite_count += 1

            # 完成
            if results["status"] != "failed":
                results["status"] = "completed"
                if callback:
                    await callback("completed", 100)

            # 补全所有Agent的结果，确保7个Agent都有明确状态
            for name in self.agents.keys():
                if name not in results["agent_results"]:
                    results["agent_results"][name] = {
                        "success": False,
                        "tokens_used": 0,
                        "duration_ms": 0,
                        "errors": ["未执行：因上游阶段失败或工作流中断导致"],
                    }

            # 收集指标
            results["metrics"] = {
                "total_tokens": sum(
                    r.get("tokens_used", 0) for r in results["agent_results"].values()
                ),
                "total_duration_ms": sum(
                    r.get("duration_ms", 0) for r in results["agent_results"].values()
                ),
                "sources_count": len(results["sources"]),
                "knowledge_nodes_count": len(orchestrator.knowledge_graph.nodes),
            }

            # 保存协调器状态（用于后续恢复或调试）
            results[
                "orchestrator_state"
            ] = await orchestrator.get_state_for_persistence()

            logger.info(
                f"[ResearchWorkflow] 工作流完成: task_id={task_id}, status={results['status']}"
            )

        except Exception as e:
            logger.error(f"[ResearchWorkflow] 工作流执行失败: {e}")
            results["status"] = "failed"
            results["errors"].append(f"工作流执行失败: {str(e)}")

            for name in self.agents.keys():
                if name not in results["agent_results"]:
                    results["agent_results"][name] = {
                        "success": False,
                        "tokens_used": 0,
                        "duration_ms": 0,
                        "errors": ["未执行：因工作流异常终止导致"],
                    }

            if callback:
                await callback("failed", 0)

        return results

    async def run_legacy(
        self,
        task_id: int,
        query: str,
        callback: Optional[Callable[[str, float], Awaitable[None]]] = None,
    ) -> AgentState:
        """
        执行工作流（旧版接口，兼容用）
        小陈说：这个是为了兼容旧代码，新代码用run方法
        """
        result = await self.run(task_id, query, callback)

        # 转换为旧格式
        state = AgentState(task_id=task_id, query=query)
        state.sources = result.get("sources", [])
        state.report_final = result.get("final_report", "")
        state.errors = result.get("errors", [])

        # 从orchestrator_state提取plan
        orchestrator_state = result.get("orchestrator_state", {})
        core_context = orchestrator_state.get("core_context", {})
        state.plan = core_context.get("research_plan", [])

        return state


# ==================== LangGraph工作流（高级版本）====================
# 小陈说：下面是使用LangGraph的高级实现，支持条件分支和循环

"""
# TODO: 完整实现LangGraph版本
# 这需要安装 langgraph 包

from langgraph.graph import StateGraph, END
from typing import TypedDict

class GraphState(TypedDict):
    task_id: int
    query: str
    orchestrator: ContextOrchestrator
    current_agent: str
    retry_count: int
    errors: list

def create_research_graph(llm_client, search_tools, model=None):
    '''
    创建LangGraph研究工作流
    小陈说：这是更高级的实现，支持条件分支、循环、重试等
    '''

    workflow = ResearchWorkflow(llm_client, search_tools, model)

    # 创建图
    graph = StateGraph(GraphState)

    # 添加节点（每个Agent一个节点）
    async def planner_node(state):
        context = await state["orchestrator"].align_context_for_agent("planner")
        result = await workflow.agents["planner"].execute(context)
        await state["orchestrator"].sync_context_after_agent("planner", result)
        return {"current_agent": "searcher" if result.success else "error"}

    async def searcher_node(state):
        context = await state["orchestrator"].align_context_for_agent("searcher")
        result = await workflow.agents["searcher"].execute(context)
        await state["orchestrator"].sync_context_after_agent("searcher", result)
        return {"current_agent": "curator" if result.success else "error"}

    # ... 其他Agent节点类似

    # 条件边：审核不通过可以重试
    def review_decision(state):
        orchestrator = state["orchestrator"]
        review_result = orchestrator.context_manager.extended_contexts.get("reviewer", {})
        if review_result.get("working_data", {}).get("review_passed"):
            return "end"
        elif state["retry_count"] < 2:
            return "revise"
        else:
            return "end"

    # 添加节点和边
    graph.add_node("planner", planner_node)
    graph.add_node("searcher", searcher_node)
    # ... 添加其他节点

    graph.set_entry_point("planner")
    graph.add_edge("planner", "searcher")
    # ... 添加其他边

    # 条件边
    graph.add_conditional_edges(
        "reviewer",
        review_decision,
        {
            "end": END,
            "revise": "writer"
        }
    )

    return graph.compile()
"""
