"""
Context Orchestrator - 多Agent系统中央协调器
负责Agent间的上下文管理和任务编排
- 分层上下文管理
- 上下文对齐和同步
- 版本控制和冲突解决
- Agent间通信协议
"""

from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json

from app.core.logging import logger
from app.orchestrator.context_manager import (
    ContextManager,
    CoreContext,
    ExtendedContext,
)
from app.orchestrator.knowledge_graph import (
    KnowledgeGraphManager,
    NodeType,
    VerificationStatus,
)


class AgentPhase(str, Enum):
    """Agent执行阶段"""

    PLANNER = "planner"
    SEARCHER = "searcher"
    CURATOR = "curator"
    ANALYZER = "analyzer"
    WRITER = "writer"
    CITER = "citer"
    REVIEWER = "reviewer"


@dataclass
class AgentMessage:
    """
    Agent间通信消息格式
    Agent间通过协调器进行间接通信
    """

    from_agent: str
    to_agent: str  # "broadcast" 表示广播给所有Agent
    message_type: str  # request/response/notification/error
    content: Dict[str, Any]
    priority: int = 0  # 优先级，越高越先处理
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "priority": self.priority,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentExecutionResult:
    """Agent执行结果"""

    agent_type: str
    success: bool
    output: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    tokens_used: int = 0
    duration_ms: int = 0
    context_changes: Dict[str, Any] = field(default_factory=dict)


class ContextOrchestrator:
    """
    中央协调器类
    负责管理所有Agent的上下文同步和通信
    """

    def __init__(self, task_id: int, query: str, llm_client=None):
        self.task_id = task_id
        self.query = query
        self.llm_client = llm_client

        # 初始化上下文管理器
        self.context_manager = ContextManager(task_id=task_id, query=query)

        # 初始化知识图谱
        self.knowledge_graph = KnowledgeGraphManager(task_id=task_id)

        # Agent消息队列
        self.message_queue: List[AgentMessage] = []

        # Agent执行历史
        self.execution_history: List[AgentExecutionResult] = []

        # 当前活跃的Agent
        self.current_agent: Optional[str] = None

        # 进度回调
        self.progress_callback: Optional[Callable[[str, float], Awaitable[None]]] = None

        # 全局错误收集
        self.global_errors: List[str] = []

        logger.info(f"[ContextOrchestrator] 初始化任务 {task_id}: {query[:50]}...")

    def set_progress_callback(
        self, callback: Callable[[str, float], Awaitable[None]]
    ) -> None:
        """设置进度回调"""
        self.progress_callback = callback

    async def report_progress(self, phase: str, progress: float) -> None:
        """报告进度"""
        if self.progress_callback:
            await self.progress_callback(phase, progress)

    # ========== 上下文对齐机制 ==========

    async def align_context_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """
        为Agent对齐上下文
        小陈说：每次Agent执行前都要调用这个，确保Agent有最新的上下文视图
        """
        logger.info(f"[ContextOrchestrator] 为Agent '{agent_type}' 对齐上下文")

        # 1. 创建执行前快照
        pre_snapshot = self.context_manager.create_snapshot(
            snapshot_type="pre_agent", agent_type=agent_type
        )

        # 2. 从知识图谱获取最新的已验证事实
        verified_facts = self.knowledge_graph.get_verified_facts()
        kg_summary = self.knowledge_graph.export_for_context()

        # 3. 更新核心上下文中的已验证事实
        self.context_manager.update_core_context(
            {
                "verified_facts": [
                    n.to_dict() for n in verified_facts[:20]
                ],  # 最多20条
                "current_phase": agent_type,
            }
        )

        # 4. 获取Agent的基础上下文
        agent_context = self.context_manager.get_context_for_agent(agent_type)
        extended_ctx = agent_context.get("extended_context", {}) or {}

        # 4.1 按阶段注入跨Agent共享数据
        # 小陈说：后面的Agent要吃前面Agent的成果，不然就都在瞎忙活

        # 统一获取搜索和筛选后的来源
        searcher_ctx = self.context_manager.extended_contexts.get("searcher")
        curator_ctx = self.context_manager.extended_contexts.get("curator")
        analyzer_ctx = self.context_manager.extended_contexts.get("analyzer")
        writer_ctx = self.context_manager.extended_contexts.get("writer")

        # 优先使用筛选后的高质量来源，其次使用原始搜索结果
        curated_sources = []
        if curator_ctx and getattr(curator_ctx, "source_references", None):
            curated_sources = list(curator_ctx.source_references)
        elif searcher_ctx and getattr(searcher_ctx, "source_references", None):
            curated_sources = list(searcher_ctx.source_references)

        # 给需要的Agent注入来源列表
        if agent_type in [
            AgentPhase.CURATOR.value,
            AgentPhase.ANALYZER.value,
            AgentPhase.WRITER.value,
            AgentPhase.CITER.value,
            AgentPhase.REVIEWER.value,
        ]:
            if curated_sources and not extended_ctx.get("source_references"):
                extended_ctx["source_references"] = curated_sources

        # 给后续写作/引用/审核阶段注入分析结果和报告草稿
        if agent_type in [
            AgentPhase.WRITER.value,
            AgentPhase.CITER.value,
            AgentPhase.REVIEWER.value,
        ]:
            # 分析阶段的中间结果（关键事实、洞察等）
            if analyzer_ctx:
                if analyzer_ctx.intermediate_results and not extended_ctx.get(
                    "intermediate_results"
                ):
                    extended_ctx["intermediate_results"] = list(
                        analyzer_ctx.intermediate_results
                    )

                if analyzer_ctx.working_data:
                    working_data = extended_ctx.get("working_data") or {}
                    for key in [
                        "analysis_summary",
                        "insights_count",
                        "key_facts_count",
                    ]:
                        if key in analyzer_ctx.working_data and key not in working_data:
                            working_data[key] = analyzer_ctx.working_data[key]
                    if working_data:
                        extended_ctx["working_data"] = working_data

            # 写作阶段生成的报告内容，供引用和审核使用
            if (
                agent_type in [AgentPhase.CITER.value, AgentPhase.REVIEWER.value]
                and writer_ctx
            ):
                if writer_ctx.working_data:
                    working_data = extended_ctx.get("working_data") or {}
                    if (
                        "report" in writer_ctx.working_data
                        and "report" not in working_data
                    ):
                        working_data["report"] = writer_ctx.working_data["report"]
                    if working_data:
                        extended_ctx["working_data"] = working_data

        agent_context["extended_context"] = extended_ctx

        # 5. 注入知识图谱摘要
        agent_context["knowledge_graph_summary"] = kg_summary

        # 6. 注入相关的消息
        agent_context["pending_messages"] = self._get_messages_for_agent(agent_type)

        # 7. 注入摘要链（如果有）
        if self.context_manager.summary_chain:
            agent_context["summary_chain"] = self.context_manager.get_summary_chain()[
                -3:
            ]  # 最近3条

        logger.debug(
            f"[ContextOrchestrator] Agent '{agent_type}' 上下文已对齐, tokens≈{agent_context['estimated_tokens']}"
        )

        return agent_context

    async def sync_context_after_agent(
        self, agent_type: str, result: AgentExecutionResult
    ) -> None:
        """
        Agent执行后同步上下文
        小陈说：Agent干完活后要把结果同步回来，不然其他Agent不知道
        """
        logger.info(f"[ContextOrchestrator] 同步Agent '{agent_type}' 的执行结果")

        # 1. 记录执行历史
        self.execution_history.append(result)

        # 2. 应用上下文变更
        if result.context_changes:
            # 更新核心上下文
            if "core" in result.context_changes:
                self.context_manager.update_core_context(result.context_changes["core"])

            # 更新扩展上下文
            if "extended" in result.context_changes:
                self.context_manager.update_extended_context(
                    agent_type, result.context_changes["extended"]
                )

        if agent_type == "reviewer":
            review_data = result.output.get("review") or {}
            if review_data:
                issues = review_data.get("issues", [])
                critical_issues = [
                    issue for issue in issues if issue.get("severity") == "critical"
                ]

                feedback = {
                    "passed": result.output.get("passed"),
                    "overall_score": review_data.get(
                        "overall_score", result.output.get("score")
                    ),
                    "critical_issues": critical_issues,
                    "suggestions": review_data.get(
                        "suggestions", result.output.get("suggestions", [])
                    ),
                }

                self.context_manager.update_core_context({"review_feedback": feedback})

        # 3. 处理Agent产生的知识节点
        if "knowledge_nodes" in result.output:
            for node_data in result.output["knowledge_nodes"]:
                self.knowledge_graph.add_node(
                    node_type=NodeType(node_data.get("type", "fact")),
                    content=node_data["content"],
                    source_ids=node_data.get("source_ids", []),
                    created_by_agent=agent_type,
                    confidence_score=node_data.get("confidence", 0.5),
                )

        # 4. 创建执行后快照
        post_snapshot = self.context_manager.create_snapshot(
            snapshot_type="post_agent", agent_type=agent_type
        )

        # 5. 检测上下文漂移
        # 小陈说：如果执行前后上下文哈希不一致，说明有变化
        if (
            post_snapshot["context_hash"]
            != self.context_manager.core_context.get_hash()
        ):
            logger.debug(f"[ContextOrchestrator] 检测到上下文变化")

        # 6. 收集错误
        if result.errors:
            self.global_errors.extend(result.errors)

    # ========== Agent间通信协议 ==========

    def send_message(self, message: AgentMessage) -> None:
        """
        发送Agent消息
        小陈说：Agent不能直接通信，必须通过我这个协调器中转
        """
        # 按优先级插入消息队列
        inserted = False
        for i, existing in enumerate(self.message_queue):
            if message.priority > existing.priority:
                self.message_queue.insert(i, message)
                inserted = True
                break
        if not inserted:
            self.message_queue.append(message)

        logger.debug(
            f"[ContextOrchestrator] 消息入队: {message.from_agent} -> {message.to_agent}"
        )

    def _get_messages_for_agent(self, agent_type: str) -> List[Dict[str, Any]]:
        """获取发给某个Agent的消息"""
        messages = []
        remaining = []

        for msg in self.message_queue:
            if msg.to_agent == agent_type or msg.to_agent == "broadcast":
                messages.append(msg.to_dict())
            else:
                remaining.append(msg)

        self.message_queue = remaining
        return messages

    def broadcast_message(
        self,
        from_agent: str,
        message_type: str,
        content: Dict[str, Any],
        priority: int = 0,
    ) -> None:
        """广播消息给所有Agent"""
        msg = AgentMessage(
            from_agent=from_agent,
            to_agent="broadcast",
            message_type=message_type,
            content=content,
            priority=priority,
        )
        self.send_message(msg)

    # ========== 上下文摘要链 ==========

    async def generate_context_summary(self) -> str:
        """
        生成当前上下文的摘要
        小陈说：上下文太长时用这个压缩信息，避免遗忘
        """
        if not self.llm_client:
            logger.warning("[ContextOrchestrator] 没有LLM客户端，跳过摘要生成")
            return ""

        # 收集需要摘要的信息
        context = self.context_manager.get_context_for_agent("summarizer")
        execution_summary = self._summarize_execution_history()
        kg_summary = self.knowledge_graph.export_for_context()

        prompt = f"""请为以下研究任务生成一个简洁的摘要（不超过500字）：

研究问题：{self.query}

当前阶段：{context["core_context"]["current_phase"]}

已完成的工作：
{execution_summary}

关键发现：
{json.dumps(kg_summary.get("key_insights", []), ensure_ascii=False)}

已验证的事实数量：{kg_summary.get("verified_count", 0)}

请生成摘要，重点包括：
1. 研究进展概述
2. 关键发现
3. 待解决的问题
"""

        try:
            # 调用LLM生成摘要
            # 注意：这里使用默认模型，如果需要自定义模型请修改此处
            response = await self.llm_client.chat.completions.create(
                model="deepseek-chat",  # 根据.env配置调整
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8192,
                temperature=0.3,
            )
            summary = response.choices[0].message.content

            # 添加到摘要链
            self.context_manager.add_to_summary_chain(summary)

            logger.info("[ContextOrchestrator] 生成上下文摘要完成")
            return summary

        except Exception as e:
            logger.error(f"[ContextOrchestrator] 生成摘要失败: {e}")
            return ""

    def _summarize_execution_history(self) -> str:
        """简要总结执行历史"""
        if not self.execution_history:
            return "暂无执行记录"

        lines = []
        for result in self.execution_history:
            status = "✓" if result.success else "✗"
            lines.append(
                f"- [{status}] {result.agent_type}: tokens={result.tokens_used}, duration={result.duration_ms}ms"
            )

        return "\n".join(lines)

    # ========== 冲突检测与解决 ==========

    async def detect_and_resolve_conflicts(self) -> List[Dict[str, Any]]:
        """
        检测并尝试解决知识冲突
        小陈说：不同Agent可能产生矛盾的信息，这里要处理
        """
        conflicts = []

        # 获取所有未验证的节点
        unverified_nodes = [
            n
            for n in self.knowledge_graph.nodes.values()
            if n.verification_status == VerificationStatus.UNVERIFIED
        ]

        # 检测潜在冲突
        for node in unverified_nodes:
            potential_conflicts = self.knowledge_graph.detect_conflicts(
                node.content, node.node_type
            )
            if potential_conflicts:
                for conflict_node in potential_conflicts:
                    if conflict_node.id != node.id:
                        conflicts.append(
                            {
                                "node1": node.to_dict(),
                                "node2": conflict_node.to_dict(),
                                "type": "potential_conflict",
                            }
                        )
                        # 标记冲突
                        self.knowledge_graph.mark_conflicting(node.id, conflict_node.id)

        if conflicts:
            logger.warning(f"[ContextOrchestrator] 检测到 {len(conflicts)} 个潜在冲突")

        return conflicts

    # ========== 窗口大小规范化 ==========

    def get_token_budget(self, agent_type: str) -> Dict[str, int]:
        """
        获取Agent的token预算
        小陈说：不同Agent有不同的token限制，要合理分配
        """
        # 基础配置（小陈说：这个可以根据模型和任务调整）
        budgets = {
            "planner": {"input": 8000, "output": 2000},
            "searcher": {"input": 4000, "output": 1000},
            "curator": {"input": 10000, "output": 3000},
            "analyzer": {"input": 12000, "output": 4000},
            "writer": {"input": 15000, "output": 8000},
            "citer": {"input": 8000, "output": 2000},
            "reviewer": {"input": 12000, "output": 3000},
        }

        return budgets.get(agent_type, {"input": 8000, "output": 2000})

    def check_token_budget(self, agent_type: str, estimated_tokens: int) -> bool:
        """检查是否超出token预算"""
        budget = self.get_token_budget(agent_type)
        if estimated_tokens > budget["input"]:
            logger.warning(
                f"[ContextOrchestrator] Agent '{agent_type}' 上下文超出预算: "
                f"{estimated_tokens} > {budget['input']}"
            )
            return False
        return True

    # ========== 主流程控制 ==========

    async def get_state_for_persistence(self) -> Dict[str, Any]:
        """
        获取可持久化的状态
        小陈说：要能保存和恢复状态，不然任务中断了就完蛋
        """
        return {
            "task_id": self.task_id,
            "query": self.query,
            "core_context": self.context_manager.core_context.to_dict(),
            "extended_contexts": {
                k: v.to_dict()
                for k, v in self.context_manager.extended_contexts.items()
            },
            "knowledge_graph": self.knowledge_graph.to_dict(),
            "execution_history": [
                {
                    "agent_type": r.agent_type,
                    "success": r.success,
                    "tokens_used": r.tokens_used,
                    "duration_ms": r.duration_ms,
                    "errors": r.errors,
                }
                for r in self.execution_history
            ],
            "summary_chain": self.context_manager.summary_chain,
            "global_errors": self.global_errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @classmethod
    def restore_from_state(
        cls, state: Dict[str, Any], llm_client=None
    ) -> "ContextOrchestrator":
        """从持久化状态恢复"""
        orchestrator = cls(
            task_id=state["task_id"], query=state["query"], llm_client=llm_client
        )

        # 恢复核心上下文
        orchestrator.context_manager.core_context = CoreContext.from_dict(
            state["core_context"]
        )

        # 恢复扩展上下文
        for agent_type, ctx_data in state.get("extended_contexts", {}).items():
            orchestrator.context_manager.extended_contexts[agent_type] = (
                ExtendedContext.from_dict(ctx_data)
            )

        # 恢复知识图谱
        if "knowledge_graph" in state:
            orchestrator.knowledge_graph = KnowledgeGraphManager.from_dict(
                state["knowledge_graph"]
            )

        # 恢复摘要链
        orchestrator.context_manager.summary_chain = state.get("summary_chain", [])

        # 恢复全局错误
        orchestrator.global_errors = state.get("global_errors", [])

        logger.info(f"[ContextOrchestrator] 从状态恢复任务 {state['task_id']}")

        return orchestrator

    def get_research_plan(self) -> List[Dict[str, Any]]:
        """获取研究计划"""
        return self.context_manager.core_context.research_plan

    def set_research_plan(self, plan: List[Dict[str, Any]]) -> None:
        """设置研究计划"""
        self.context_manager.update_core_context({"research_plan": plan})

    def get_final_report(self) -> Optional[str]:
        """获取最终报告"""
        writer_ctx = self.context_manager.extended_contexts.get("writer")
        if writer_ctx and "report" in writer_ctx.working_data:
            return writer_ctx.working_data["report"]
        return None

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """获取所有来源"""
        searcher_ctx = self.context_manager.extended_contexts.get("searcher")
        if searcher_ctx:
            return searcher_ctx.source_references
        return []
