"""
Pydantic 请求/响应模型
小陈说：数据验证这玩意，省得前端传一堆垃圾参数过来
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

from app.db.models import TaskStatus, AgentType


# ============ 研究任务相关 Schema ============


class ResearchTaskCreate(BaseModel):
    """创建研究任务的请求体"""

    query: str = Field(..., min_length=1, max_length=2000, description="研究问题")
    config: Optional[dict] = Field(default=None, description="任务配置")


class ResearchTaskUpdate(BaseModel):
    """更新研究任务的请求体"""

    status: Optional[TaskStatus] = None
    progress: Optional[float] = Field(default=None, ge=0, le=100)


class PlanItemSchema(BaseModel):
    """计划项Schema"""

    id: int
    title: str
    description: Optional[str] = None
    status: str
    order: int
    parent_id: Optional[int] = None
    children: Optional[List["PlanItemSchema"]] = None

    class Config:
        from_attributes = True


class SourceSchema(BaseModel):
    """信息来源Schema"""

    id: int
    title: str
    url: Optional[str] = None
    source_type: str
    content: Optional[str] = None
    confidence: str
    relevance_score: float
    created_at: datetime

    class Config:
        from_attributes = True


class ChartSchema(BaseModel):
    """图表Schema"""

    id: int
    chart_type: str
    title: str
    description: Optional[str] = None
    data: dict
    config: Optional[dict] = None
    section: str
    order: int
    created_by_agent: AgentType
    created_at: datetime

    class Config:
        from_attributes = True


class AgentLogSchema(BaseModel):
    """Agent日志Schema"""

    id: int
    agent_type: AgentType
    action: str
    content: str
    status: str
    tokens_used: int
    duration_ms: int
    created_at: datetime

    class Config:
        from_attributes = True


class ResearchTaskResponse(BaseModel):
    """研究任务响应"""

    id: int
    query: str
    status: TaskStatus
    progress: float
    config: Optional[dict] = None
    report_content: Optional[str] = None
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ResearchTaskDetailResponse(ResearchTaskResponse):
    """研究任务详情响应（包含关联数据）"""

    plan_items: List[PlanItemSchema] = []
    sources: List[SourceSchema] = []
    recent_logs: List[AgentLogSchema] = []
    charts: List[ChartSchema] = []


class ResearchTaskListResponse(BaseModel):
    """研究任务列表响应"""

    total: int
    items: List[ResearchTaskResponse]


# ============ Agent 相关 Schema ============


class AgentStatusSchema(BaseModel):
    """单个Agent状态"""

    agent_type: AgentType
    status: str  # active, idle, completed
    current_task: Optional[str] = None
    progress: float = 0
    metrics: dict = Field(default_factory=dict)
    sub_tasks: List[dict] = []
    output_content: str = ""


class AgentActivityResponse(BaseModel):
    """Agent活动状态响应"""

    task_id: int
    agents: List[AgentStatusSchema]
    overall_progress: float


# ============ WebSocket 消息 Schema ============


class WSMessage(BaseModel):
    """WebSocket消息基类"""

    type: str
    task_id: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict = Field(default_factory=dict)


class WSAgentLog(WSMessage):
    """Agent日志WebSocket消息"""

    type: str = "agent_log"
    agent_type: AgentType
    action: str
    content: str
    status: str = "info"


class WSProgressUpdate(WSMessage):
    """进度更新WebSocket消息"""

    type: str = "progress"
    progress: float
    stage: str


class WSPlanUpdate(WSMessage):
    """计划更新WebSocket消息"""

    type: str = "plan_update"
    plan_item_id: int
    new_status: str


class WSSourceAdded(WSMessage):
    """新来源添加WebSocket消息"""

    type: str = "source_added"
    source: SourceSchema


# 允许递归引用
PlanItemSchema.model_rebuild()
