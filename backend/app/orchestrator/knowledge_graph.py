"""知识图谱管理器"""

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
    """知识图谱节点"""

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
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeNode":
        data["node_type"] = NodeType(data["node_type"])
        data["verification_status"] = VerificationStatus(data["verification_status"])
        return cls(**data)


class KnowledgeGraphManager:
    """知识图谱管理器"""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.nodes: Dict[str, KnowledgeNode] = {}  # id -> node
        self.node_counter = 0

        # 索引优化
        self.content_index: Dict[str, List[str]] = {}  # word -> [node_ids]
        self.type_index: Dict[NodeType, List[str]] = {}  # type -> [node_ids]
        self.agent_index: Dict[str, List[str]] = {}  # agent -> [node_ids]
        self.query_cache: Dict[str, List[str]] = {}  # query -> cached_results
        self.index_stats = {
            "total_nodes": 0,
            "index_updates": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

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
        metadata: Dict[str, Any] = None,
    ) -> KnowledgeNode:
        """添加知识节点"""
        node_id = self._generate_node_id()
        node = KnowledgeNode(
            id=node_id,
            node_type=node_type,
            content=content,
            source_ids=source_ids or [],
            created_by_agent=created_by_agent,
            confidence_score=confidence_score,
            related_node_ids=related_node_ids or [],
            metadata=metadata or {},
        )

        self.nodes[node_id] = node

        # 更新索引
        self._update_indices(node)

        self.index_stats["total_nodes"] += 1
        logger.info(
            f"[KnowledgeGraph] 添加节点: {node_id}, type={node_type.value}, agent={created_by_agent}"
        )

        return node

    def _update_indices(self, node: KnowledgeNode):
        """更新所有索引"""
        # 1. 内容索引 - 分词并建立倒排索引
        self._update_content_index(node)

        # 2. 类型索引
        if node.node_type not in self.type_index:
            self.type_index[node.node_type] = []
        self.type_index[node.node_type].append(node.id)

        # 3. Agent索引
        if node.created_by_agent not in self.agent_index:
            self.agent_index[node.created_by_agent] = []
        self.agent_index[node.created_by_agent].append(node.id)

        self.index_stats["index_updates"] += 1

    def _update_content_index(self, node: KnowledgeNode):
        """更新内容倒排索引"""
        # 简单的中文分词（按标点和空格分割）
        words = self._tokenize_content(node.content)

        for word in words:
            if word not in self.content_index:
                self.content_index[word] = []
            if node.id not in self.content_index[word]:
                self.content_index[word].append(node.id)

    def _tokenize_content(self, content: str) -> List[str]:
        """简单的内容分词"""
        import re

        # 移除标点，分割成词
        cleaned = re.sub(r"[^\w\s\u4e00-\u9fff]", "", content.lower())
        return [word for word in cleaned.split() if len(word) > 1]

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        """获取节点"""
        return self.nodes.get(node_id)

    def update_node(
        self, node_id: str, updates: Dict[str, Any]
    ) -> Optional[KnowledgeNode]:
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
        """验证节点"""
        node = self.nodes.get(node_id)
        if not node:
            return False

        node.verification_count += 1

        # 根据验证次数调整置信度
        if node.verification_count >= 2:
            node.verification_status = VerificationStatus.VERIFIED
            node.confidence_score = min(1.0, node.confidence_score + 0.2)

        node.updated_at = datetime.utcnow().isoformat()

        logger.info(
            f"[KnowledgeGraph] 节点 {node_id} 被 {verifier_agent} 验证, count={node.verification_count}"
        )
        return True

    def mark_conflicting(self, node_id: str, conflicting_node_id: str) -> None:
        """标记冲突节点"""
        node = self.nodes.get(node_id)
        if node:
            node.verification_status = VerificationStatus.CONFLICTING
            if conflicting_node_id not in node.related_node_ids:
                node.related_node_ids.append(conflicting_node_id)
            logger.warning(
                f"[KnowledgeGraph] 节点 {node_id} 与 {conflicting_node_id} 冲突"
            )

    def get_verified_facts(self) -> List[KnowledgeNode]:
        """获取所有已验证的事实"""
        return [
            node
            for node in self.nodes.values()
            if node.verification_status == VerificationStatus.VERIFIED
        ]

    def get_facts_by_agent(self, agent_type: str) -> List[KnowledgeNode]:
        """获取某个Agent创建的所有节点"""
        return [
            node for node in self.nodes.values() if node.created_by_agent == agent_type
        ]

    def get_high_confidence_nodes(self, threshold: float = 0.7) -> List[KnowledgeNode]:
        """获取高置信度节点"""
        return [
            node for node in self.nodes.values() if node.confidence_score >= threshold
        ]

    def search_nodes(self, keyword: str) -> List[KnowledgeNode]:
        """
        搜索包含关键词的节点（索引优化版）
        使用倒排索引进行高效查询
        """
        # 检查缓存
        cache_key = f"search_{keyword}"
        if cache_key in self.query_cache:
            self.index_stats["cache_hits"] += 1
            node_ids = self.query_cache[cache_key]
            return [self.nodes[nid] for nid in node_ids if nid in self.nodes]
        else:
            self.index_stats["cache_misses"] += 1

        # 使用索引进行搜索
        keyword_lower = keyword.lower()
        candidate_ids = set()

        # 1. 使用内容索引查找候选节点
        query_words = self._tokenize_content(keyword)
        for word in query_words:
            if word in self.content_index:
                candidate_ids.update(self.content_index[word])

        # 2. 如果没有找到候选，使用传统方法作为fallback
        if not candidate_ids:
            candidate_ids = {
                node_id
                for node_id, node in self.nodes.items()
                if keyword_lower in node.content.lower()
            }

        # 3. 转换为节点列表
        results = [
            self.nodes[node_id] for node_id in candidate_ids if node_id in self.nodes
        ]

        # 4. 更新缓存（限制缓存大小）
        if len(self.query_cache) < 100:  # 最多缓存100个查询
            self.query_cache[cache_key] = list(candidate_ids)

        return results

    def get_related_nodes(self, node_id: str) -> List[KnowledgeNode]:
        """获取相关节点"""
        node = self.nodes.get(node_id)
        if not node:
            return []

        return [self.nodes[rid] for rid in node.related_node_ids if rid in self.nodes]

    def detect_conflicts(
        self, new_content: str, node_type: NodeType
    ) -> List[KnowledgeNode]:
        """检测与新内容可能冲突的节点"""
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
        """导出用于上下文的知识图谱摘要"""
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
                n.content for n in self.nodes.values() if n.node_type == NodeType.ENTITY
            ][:10],
            "key_insights": [
                n.content
                for n in self.nodes.values()
                if n.node_type == NodeType.INSIGHT and n.confidence_score >= 0.6
            ][:5],
        }

    def to_dict(self) -> Dict[str, Any]:
        """序列化整个知识图谱"""
        return {
            "task_id": self.task_id,
            "node_counter": self.node_counter,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KnowledgeGraphManager":
        """反序列化"""
        manager = cls(task_id=data["task_id"])
        manager.node_counter = data["node_counter"]
        manager.nodes = {
            k: KnowledgeNode.from_dict(v) for k, v in data["nodes"].items()
        }
        return manager
