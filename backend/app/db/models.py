"""数据库模型"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    Integer,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    Enum,
    Boolean,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.database import Base
import hashlib
import json


class TaskStatus(enum.Enum):
    """研究任务状态枚举"""

    PENDING = "pending"
    PLANNING = "planning"
    SEARCHING = "searching"
    CURATING = "curating"
    ANALYZING = "analyzing"
    WRITING = "writing"
    CITING = "citing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentType(enum.Enum):
    """7个Agent类型枚举"""

    PLANNER = "planner"
    SEARCHER = "searcher"
    CURATOR = "curator"
    ANALYZER = "analyzer"
    WRITER = "writer"
    CITER = "citer"
    REVIEWER = "reviewer"


class ResearchTask(Base):
    """研究任务表"""

    __tablename__ = "research_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(Text, nullable=False, comment="研究问题")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态"
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, comment="进度百分比")
    config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="任务配置"
    )
    report_content: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="报告内容"
    )
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="摘要")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 关联
    plan_items: Mapped[list["PlanItem"]] = relationship(
        "PlanItem", back_populates="task", cascade="all, delete-orphan"
    )
    agent_logs: Mapped[list["AgentLog"]] = relationship(
        "AgentLog", back_populates="task", cascade="all, delete-orphan"
    )
    sources: Mapped[list["Source"]] = relationship(
        "Source", back_populates="task", cascade="all, delete-orphan"
    )
    knowledge_nodes: Mapped[list["KnowledgeNode"]] = relationship(
        "KnowledgeNode", back_populates="task", cascade="all, delete-orphan"
    )
    context_snapshots: Mapped[list["ContextSnapshot"]] = relationship(
        "ContextSnapshot", back_populates="task", cascade="all, delete-orphan"
    )
    charts: Mapped[list["Chart"]] = relationship(
        "Chart", back_populates="task", cascade="all, delete-orphan"
    )


class PlanItem(Base):
    """研究计划项 - 树形结构"""

    __tablename__ = "plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("plan_items.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    task: Mapped["ResearchTask"] = relationship(
        "ResearchTask", back_populates="plan_items"
    )
    children: Mapped[list["PlanItem"]] = relationship(
        "PlanItem", backref="parent", remote_side=[id]
    )


class AgentLog(Base):
    """Agent执行日志"""

    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType))
    action: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="info")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["ResearchTask"] = relationship(
        "ResearchTask", back_populates="agent_logs"
    )


class Source(Base):
    """信息来源表"""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    source_type: Mapped[str] = mapped_column(String(50), default="web")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(20), default="medium")
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_curated: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否经过Curator筛选"
    )
    source_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="来源元数据"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["ResearchTask"] = relationship(
        "ResearchTask", back_populates="sources"
    )


class KnowledgeNode(Base):
    """知识图谱节点"""

    __tablename__ = "knowledge_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))

    # 节点内容
    node_type: Mapped[str] = mapped_column(
        String(50), comment="节点类型: fact/entity/relation/insight"
    )
    content: Mapped[str] = mapped_column(Text, comment="节点内容")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="摘要")

    # 来源追踪
    source_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="来源ID列表"
    )
    created_by_agent: Mapped[AgentType] = mapped_column(
        Enum(AgentType), comment="创建该节点的Agent"
    )

    # 验证状态
    is_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已验证"
    )
    confidence_score: Mapped[float] = mapped_column(
        Float, default=0.5, comment="置信度分数"
    )
    verification_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="被验证次数"
    )

    # 版本控制
    version: Mapped[int] = mapped_column(Integer, default=1)
    previous_version_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 关系
    related_node_ids: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True, comment="相关节点ID"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    task: Mapped["ResearchTask"] = relationship(
        "ResearchTask", back_populates="knowledge_nodes"
    )


class ContextSnapshot(Base):
    """上下文快照"""

    __tablename__ = "context_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))

    # 快照信息
    snapshot_type: Mapped[str] = mapped_column(
        String(50), comment="快照类型: pre_agent/post_agent/sync/conflict_resolution"
    )
    agent_type: Mapped[Optional[AgentType]] = mapped_column(
        Enum(AgentType), nullable=True
    )

    # 核心上下文
    core_context: Mapped[dict] = mapped_column(JSON, comment="核心上下文数据")

    # 扩展上下文
    extended_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 上下文摘要（用于长上下文场景）
    context_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 版本信息
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Token统计
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["ResearchTask"] = relationship(
        "ResearchTask", back_populates="context_snapshots"
    )


class Chart(Base):
    """图表数据"""

    __tablename__ = "charts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("research_tasks.id"))

    # 图表基本信息
    chart_type: Mapped[str] = mapped_column(
        String(50), comment="图表类型: bar/line/pie/scatter/area 等"
    )
    title: Mapped[str] = mapped_column(String(200), comment="图表标题")
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="图表描述"
    )

    # 图表数据
    data: Mapped[dict] = mapped_column(
        JSON, comment="图表数据，包含 series、categories 等"
    )
    config: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="图表配置，如颜色、样式等"
    )

    # 位置信息
    section: Mapped[str] = mapped_column(
        String(100), comment="报告章节，如 '主要发现', '趋势分析' 等"
    )
    order: Mapped[int] = mapped_column(Integer, default=0, comment="在章节内的排序")

    # 创建信息
    created_by_agent: Mapped[AgentType] = mapped_column(
        Enum(AgentType), comment="创建该图表的Agent"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["ResearchTask"] = relationship("ResearchTask", back_populates="charts")


class CacheEntry(Base):
    """
    缓存条目 - 用于缓存LLM响应、搜索结果等
    支持TTL过期和访问统计
    """

    __tablename__ = "cache_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # 缓存键和值
    cache_key: Mapped[str] = mapped_column(
        String(128), unique=True, index=True, comment="缓存键（MD5哈希值）"
    )
    cache_value: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="缓存值（JSON序列化）"
    )

    # 缓存类型和元数据
    cache_type: Mapped[str] = mapped_column(
        String(50),
        index=True,
        comment="缓存类型：llm_response/search_result/context/report_fragment",
    )
    cache_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="元数据，如原始查询参数、模型信息等"
    )

    # 时间管理
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="过期时间"
    )

    # 访问统计
    access_count: Mapped[int] = mapped_column(Integer, default=0, comment="访问次数")
    last_accessed: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后访问时间"
    )

    # 压缩和大小信息
    is_compressed: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="是否已压缩"
    )
    value_size: Mapped[int] = mapped_column(
        Integer, default=0, comment="原始值大小（字节）"
    )

    @classmethod
    def generate_key(cls, content: str, cache_type: str = "") -> str:
        """生成缓存键"""
        key_content = f"{cache_type}:{content}"
        return hashlib.md5(key_content.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    def touch(self):
        """更新最后访问时间和访问计数"""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1
