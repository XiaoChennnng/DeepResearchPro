"""
知识图谱管理器
小陈说：这是单一事实来源（Single Source of Truth），所有已确认的信息都存这里
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import logger


class NodeType(str, Enum):
    """知识节点类型"""
    FACT = "fact"  # 事实
    ENTITY = "entity"  # 实体
    RELATION = "relation"  # 关系
    INSIGHT = "insight"  # 洞察
    CLAIM = "claim"  # 待验证的声明


class VerificationStatus(str, Enum):
    """验证状态"""
    UNVERIFIED = "unverified"  # 未验证
    VERIFIED = "verified"  # 已验证
    CONFLICTING = "conflicting"  # 存在冲突
    DEPRECATED = "deprecated"  # 已废弃


@dataclass
class KnowledgeNode:
    """
    知识图谱节点
    小陈说：每个节点代表一条知识，必须有来源追踪
    """
    id: str
    node_type: NodeType
    content: str
    source_ids: List[int] = field(default_factory=list)  # 来源ID列表
    created_by_agent: str = ""  # 创建该节点的Agent
    confidence_score: float = 0.5  # 置信度 0-1
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verification_count: int = 0  # 被验证次数
    related_node_ids: List[str] = field(default_factory=list)  # 相关节点
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "content": self.content,
            "source_ids": self.source_ids,
            "created_by_agent": self.created_by_agent,
            "confidence_score": self.confidence_score,
            "verification_status": self.verification_status.value,
            "verification_count": self.verification_count,
            "related_node_ids": self.related_node_ids,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeNode":
        data["node_type"] = NodeType(data["node_type"])
        data["verification_status"] = VerificationStatus(data["verification_status"])
        return cls(**data)


class KnowledgeGraphManager:
    """
    知识图谱管理器
    小陈说：管理所有已确认的知识，提供查询、验证、冲突检测等功能
    """

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.nodes: Dict[str, KnowledgeNode] = {}  # id -> node
        self.node_counter = 0

        logger.info(f"[KnowledgeGraph] 初始化任务 {task_id} 的知识图谱")

    def _generate_node_id(self) -> str:
        """生成唯一节点ID"""
        self.node_counter += 1
        return f"node_{self.task_id}_{self.node_counter}"

    def add_node(
        self,
        node_type: NodeType,
        content: str,
        source_ids: List[int] = None,
        created_by_agent: str = "",
        confidence_score: float = 0.5,
        related_node_ids: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> KnowledgeNode:
        """
        添加知识节点
        小陈说：每条新知识都要记录来源，不然就是在造谣
        """
        node_id = self._generate_node_id()
        node = KnowledgeNode(
            id=node_id,
            node_type=node_type,
            content=content,
            source_ids=source_ids or [],
            created_by_agent=created_by_agent,
            confidence_score=confidence_score,
            related_node_ids=related_node_ids or [],
            metadata=metadata or {}
        )

        self.nodes[node_id] = node
        logger.info(f"[KnowledgeGraph] 添加节点: {node_id}, type={node_type.value}, agent={created_by_agent}")

        return node

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def update_node(self, node_id: str, updates: Dict[str, Any]) -> Optional[KnowledgeNode]:
        """更新节点"""
        node = self.nodes.get(node_id)
        if not node:
            logger.warning(f"[KnowledgeGraph] 节点不存在: {node_id}")
            return None

        for key, value in updates.items():
            if hasattr(node, key):
                setattr(node, key, value)

        node.updated_at = datetime.utcnow().isoformat()
        node.version += 1

        logger.debug(f"[KnowledgeGraph] 更新节点: {node_id}, version={node.version}")
        return node

    def verify_node(self, node_id: str, verifier_agent: str) -> bool:
        """
        验证节点
        小陈说：被多个Agent验证的信息更可信
        """
        node = self.nodes.get(node_id)
        if not node:
            return False

        node.verification_count += 1

        # 根据验证次数调整置信度
        if node.verification_count >= 2:
            node.verification_status = VerificationStatus.VERIFIED
            node.confidence_score = min(1.0, node.confidence_score + 0.2)

        node.updated_at = datetime.utcnow().isoformat()

        logger.info(f"[KnowledgeGraph] 节点 {node_id} 被 {verifier_agent} 验证, count={node.verification_count}")
        return True

    def mark_conflicting(self, node_id: str, conflicting_node_id: str) -> None:
        """标记冲突节点"""
        node = self.nodes.get(node_id)
        if node:
            node.verification_status = VerificationStatus.CONFLICTING
            if conflicting_node_id not in node.related_node_ids:
                node.related_node_ids.append(conflicting_node_id)
            logger.warning(f"[KnowledgeGraph] 节点 {node_id} 与 {conflicting_node_id} 冲突")

    def get_verified_facts(self) -> List[KnowledgeNode]:
        """
        获取所有已验证的事实
        小陈说：只返回可信的信息给其他Agent
        """
        return [
            node for node in self.nodes.values()
            if node.verification_status == VerificationStatus.VERIFIED
        ]

    def get_facts_by_agent(self, agent_type: str) -> List[KnowledgeNode]:
        """获取某个Agent创建的所有节点"""
        return [
            node for node in self.nodes.values()
            if node.created_by_agent == agent_type
        ]

    def get_high_confidence_nodes(self, threshold: float = 0.7) -> List[KnowledgeNode]:
        """获取高置信度节点"""
        return [
            node for node in self.nodes.values()
            if node.confidence_score >= threshold
        ]

    def search_nodes(self, keyword: str) -> List[KnowledgeNode]:
        """
        搜索包含关键词的节点
        小陈说：简单的关键词匹配，后面可以接向量搜索
        """
        keyword_lower = keyword.lower()
        return [
            node for node in self.nodes.values()
            if keyword_lower in node.content.lower()
        ]

    def get_related_nodes(self, node_id: str) -> List[KnowledgeNode]:
        """获取相关节点"""
        node = self.nodes.get(node_id)
        if not node:
            return []

        return [
            self.nodes[rid] for rid in node.related_node_ids
            if rid in self.nodes
        ]

    def detect_conflicts(self, new_content: str, node_type: NodeType) -> List[KnowledgeNode]:
        """
        检测与新内容可能冲突的节点
        小陈说：简单实现，后面可以用LLM来做语义冲突检测
        """
        # 这里是简化实现，实际应该用语义相似度
        potential_conflicts = []
        for node in self.nodes.values():
            if node.node_type == node_type:
                # 简单的关键词重叠检测
                new_words = set(new_content.lower().split())
                existing_words = set(node.content.lower().split())
                overlap = len(new_words & existing_words)
                if overlap > 3:  # 超过3个词重叠
                    potential_conflicts.append(node)

        return potential_conflicts

    def export_for_context(self) -> Dict[str, Any]:
        """
        导出用于上下文的知识图谱摘要
        小陈说：给Agent的上下文不需要全部节点，只要关键信息
        """
        verified = self.get_verified_facts()
        high_confidence = self.get_high_confidence_nodes()

        return {
            "total_nodes": len(self.nodes),
            "verified_count": len(verified),
            "high_confidence_count": len(high_confidence),
            "verified_facts": [
                {"id": n.id, "type": n.node_type.value, "content": n.content[:200]}
                for n in verified[:20]  # 最多20条
            ],
            "key_entities": [
                n.content for n in self.nodes.values()
                if n.node_type == NodeType.ENTITY
            ][:10],
            "key_insights": [
                n.content for n in self.nodes.values()
                if n.node_type == NodeType.INSIGHT and n.confidence_score >= 0.6
            ][:5]
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化整个知识图谱"""
        return {
            "task_id": self.task_id,
            "node_counter": self.node_counter,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraphManager":
        """反序列化"""
        manager = cls(task_id=data["task_id"])
        manager.node_counter = data["node_counter"]
        manager.nodes = {
            k: KnowledgeNode.from_dict(v)
            for k, v in data["nodes"].items()
        }
        return manager
