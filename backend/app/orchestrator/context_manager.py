"""
分层上下文管理器
小陈说：这玩意儿管理核心上下文和扩展上下文，确保Agent不会遗忘关键信息
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
import hashlib
import json

from app.core.logging import logger


@dataclass
class CoreContext:
    """
    核心上下文 - 所有Agent必须知道的信息
    小陈说：这是每个Agent调用前必须注入的核心数据，丢了就完蛋
    """
    task_id: int
    query: str  # 原始研究问题
    research_plan: List[Dict[str, Any]] = field(default_factory=list)  # 研究计划大纲
    verified_facts: List[Dict[str, Any]] = field(default_factory=list)  # 已验证的事实（来自知识图谱）
    current_phase: str = "pending"
    key_entities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    review_feedback: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "query": self.query,
            "research_plan": self.research_plan,
            "verified_facts": self.verified_facts,
            "current_phase": self.current_phase,
            "key_entities": self.key_entities,
            "constraints": self.constraints,
            "review_feedback": self.review_feedback,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoreContext":
        return cls(**data)

    def get_hash(self) -> str:
        """计算上下文哈希，用于版本比对"""
        content = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class ExtendedContext:
    """
    扩展上下文 - 特定Agent的工作数据
    小陈说：这是Agent干活时的临时数据，可以丢但最好别丢
    """
    agent_type: str
    working_data: Dict[str, Any] = field(default_factory=dict)  # Agent工作数据
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)  # 中间结果
    source_references: List[Dict[str, Any]] = field(default_factory=list)  # 引用来源
    notes: List[str] = field(default_factory=list)  # Agent备注

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_type": self.agent_type,
            "working_data": self.working_data,
            "intermediate_results": self.intermediate_results,
            "source_references": self.source_references,
            "notes": self.notes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtendedContext":
        return cls(**data)


class ContextManager:
    """
    上下文管理器
    小陈说：负责管理核心上下文和扩展上下文，支持版本控制和上下文摘要
    """

    # Token限制配置（小陈说：这个要根据模型调整）
    MAX_CORE_CONTEXT_TOKENS = 4000  # 核心上下文最大token数
    MAX_EXTENDED_CONTEXT_TOKENS = 8000  # 扩展上下文最大token数
    SUMMARIZATION_THRESHOLD = 0.8  # 触发摘要的阈值

    def __init__(self, task_id: int, query: str):
        self.task_id = task_id
        self.core_context = CoreContext(task_id=task_id, query=query)
        self.extended_contexts: Dict[str, ExtendedContext] = {}
        self.context_history: List[Dict[str, Any]] = []  # 上下文历史（用于版本控制）
        self.summary_chain: List[str] = []  # 摘要链

        logger.info(f"[ContextManager] 初始化任务 {task_id} 的上下文管理器")

    def update_core_context(self, updates: Dict[str, Any]) -> None:
        """
        更新核心上下文
        小陈说：每次更新都要记录历史，方便回溯
        """
        # 记录更新前的状态
        old_hash = self.core_context.get_hash()
        old_state = self.core_context.to_dict()

        # 应用更新
        for key, value in updates.items():
            if hasattr(self.core_context, key):
                setattr(self.core_context, key, value)

        # 记录历史
        new_hash = self.core_context.get_hash()
        if old_hash != new_hash:
            self.context_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "type": "core_update",
                "old_hash": old_hash,
                "new_hash": new_hash,
                "changes": {k: v for k, v in updates.items() if k in old_state}
            })
            logger.debug(f"[ContextManager] 核心上下文已更新: {list(updates.keys())}")

    def get_or_create_extended_context(self, agent_type: str) -> ExtendedContext:
        """获取或创建Agent的扩展上下文"""
        if agent_type not in self.extended_contexts:
            self.extended_contexts[agent_type] = ExtendedContext(agent_type=agent_type)
            logger.debug(f"[ContextManager] 创建Agent '{agent_type}' 的扩展上下文")
        return self.extended_contexts[agent_type]

    def update_extended_context(self, agent_type: str, updates: Dict[str, Any]) -> None:
        """更新Agent的扩展上下文"""
        ctx = self.get_or_create_extended_context(agent_type)
        for key, value in updates.items():
            if hasattr(ctx, key):
                if isinstance(getattr(ctx, key), list) and isinstance(value, list):
                    # 列表类型追加
                    getattr(ctx, key).extend(value)
                elif isinstance(getattr(ctx, key), dict) and isinstance(value, dict):
                    # 字典类型合并
                    getattr(ctx, key).update(value)
                else:
                    setattr(ctx, key, value)
        logger.debug(f"[ContextManager] Agent '{agent_type}' 的扩展上下文已更新")

    def estimate_tokens(self, text: str) -> int:
        """
        估算文本的token数量
        小陈说：粗略估算，中文按2字符1token，英文按4字符1token
        """
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return chinese_chars // 2 + other_chars // 4

    def get_context_for_agent(self, agent_type: str) -> Dict[str, Any]:
        """
        获取给Agent的完整上下文
        小陈说：这是Agent调用前必须拿到的数据包
        """
        core = self.core_context.to_dict()
        extended = self.get_or_create_extended_context(agent_type).to_dict()

        # 检查是否需要摘要
        context_str = json.dumps({"core": core, "extended": extended}, ensure_ascii=False)
        estimated_tokens = self.estimate_tokens(context_str)

        total_limit = self.MAX_CORE_CONTEXT_TOKENS + self.MAX_EXTENDED_CONTEXT_TOKENS
        if estimated_tokens > total_limit * self.SUMMARIZATION_THRESHOLD:
            logger.warning(f"[ContextManager] 上下文接近阈值 ({estimated_tokens} tokens)，可能需要摘要")

        return {
            "core_context": core,
            "extended_context": extended,
            "context_hash": self.core_context.get_hash(),
            "estimated_tokens": estimated_tokens
        }

    def create_snapshot(self, snapshot_type: str, agent_type: Optional[str] = None) -> Dict[str, Any]:
        """
        创建上下文快照
        小陈说：每次Agent执行前后都要拍个快照，出问题好追溯
        """
        snapshot = {
            "snapshot_type": snapshot_type,
            "agent_type": agent_type,
            "timestamp": datetime.utcnow().isoformat(),
            "core_context": self.core_context.to_dict(),
            "extended_contexts": {k: v.to_dict() for k, v in self.extended_contexts.items()},
            "context_hash": self.core_context.get_hash(),
            "version": len(self.context_history) + 1
        }
        logger.info(f"[ContextManager] 创建快照: type={snapshot_type}, version={snapshot['version']}")
        return snapshot

    def add_to_summary_chain(self, summary: str) -> None:
        """
        添加摘要到摘要链
        小陈说：长上下文场景用递归摘要来压缩信息
        """
        self.summary_chain.append({
            "timestamp": datetime.utcnow().isoformat(),
            "summary": summary,
            "context_hash": self.core_context.get_hash()
        })
        logger.debug(f"[ContextManager] 摘要链长度: {len(self.summary_chain)}")

    def get_summary_chain(self) -> List[str]:
        """获取摘要链"""
        return [item["summary"] for item in self.summary_chain]

    def detect_drift(self, other_hash: str) -> bool:
        """
        检测上下文漂移
        小陈说：如果哈希不一致，说明上下文发生了变化，需要同步
        """
        current_hash = self.core_context.get_hash()
        is_drifted = current_hash != other_hash
        if is_drifted:
            logger.warning(f"[ContextManager] 检测到上下文漂移: {other_hash} -> {current_hash}")
        return is_drifted
