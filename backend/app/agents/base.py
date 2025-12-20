"""
Agent基类
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
import time
import json
import asyncio

from openai import AsyncOpenAI

from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


@dataclass
class AgentState:
    """Agent状态数据类"""

    task_id: int
    query: str
    current_stage: str = ""

    # 计划数据
    plan: list = field(default_factory=list)

    # 搜索结果
    sources: list = field(default_factory=list)

    # 分析数据
    analysis_results: dict = field(default_factory=dict)

    # 报告内容
    report_draft: str = ""
    report_final: str = ""

    # 审核结果
    review_issues: list = field(default_factory=list)

    # 执行指标
    metrics: dict = field(default_factory=dict)

    # 错误信息
    errors: list = field(default_factory=list)


class BaseAgent(ABC):
    """Agent基类"""

    def __init__(
        self,
        agent_type: AgentType,
        name: str,
        llm_client: Optional[AsyncOpenAI] = None,
        model: Optional[str] = None,
        llm_factory: Optional[Any] = None,
        status_callback: Optional[Callable] = None,
    ):
        self.agent_type = agent_type
        self.name = name
        self.llm_client = llm_client
        self.model = model or (
            llm_factory.get_model() if llm_factory else "gpt-4o-mini"
        )
        self.llm_factory = llm_factory
        self.status_callback = status_callback
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.tokens_used: int = 0
        self.api_calls: int = 0
        self.current_subtask: str = ""
        self.output_content: str = ""

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

    async def update_subtask(self, subtask: str) -> None:
        """更新当前子任务"""
        self.current_subtask = subtask
        # 异步发送状态更新
        if self.status_callback:
            await self.status_callback(
                {
                    "agent_type": self.agent_type.value,
                    "api_calls": self.api_calls,
                    "tokens_used": self.tokens_used,
                    "current_subtask": self.current_subtask,
                    "output_content": self.output_content[:500],
                    "duration_ms": self.get_metrics()["duration_ms"],
                    "subtask_update": True,  # 标记这是一个子任务更新
                }
            )

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """执行Agent任务"""
        pass

    async def run(self, state: AgentState) -> AgentState:
        """执行Agent任务（旧版接口）"""
        # 转换为新格式调用
        context = {
            "core_context": {
                "task_id": state.task_id,
                "query": state.query,
                "research_plan": state.plan,
                "current_phase": state.current_stage,
                "verified_facts": [],
                "key_entities": [],
                "constraints": [],
            },
            "extended_context": {
                "agent_type": self.agent_type.value,
                "working_data": {},
                "intermediate_results": [],
                "source_references": state.sources,
                "notes": [],
            },
        }

        result = await self.execute(context)

        # 将结果转换回旧格式
        if result.success:
            output = result.output
            if "plan" in output:
                state.plan = output["plan"]
            if "sources" in output:
                state.sources = output["sources"]
            if "analysis" in output:
                state.analysis_results = output["analysis"]
            if "report" in output:
                state.report_draft = output["report"]
            if "review" in output:
                state.review_issues = output.get("issues", [])
                if output.get("passed"):
                    state.report_final = state.report_draft

        state.errors.extend(result.errors)
        state.metrics[self.agent_type.value] = {
            "tokens_used": result.tokens_used,
            "duration_ms": result.duration_ms,
        }

        return state

    def _clamp_max_tokens(self, requested_tokens: int) -> int:
        """限制max_tokens不超过提供商上限"""
        from app.core.llm_factory import LLMProvider

        # 各大模型提供商的max_tokens限制（这是API的实际输出限制，不是上下文窗口！）
        provider_limits = {
            LLMProvider.DEEPSEEK: 8192,  # deepseek-chat 支持8192（改为deepseek-chat后）
            LLMProvider.OPENAI: 16384,  # GPT-4o最大16384
            LLMProvider.QWEN: 32768,  # 通义千问最大32768
            LLMProvider.ZHIPU: 8192,  # 智谱AI最大8192
            LLMProvider.MOONSHOT: 32768,  # 月之暗面最大32768
            LLMProvider.YI: 16384,  # 零一万物最大16384
            LLMProvider.BAICHUAN: 16384,  # 百川智能最大16384
            LLMProvider.MINIMAX: 32768,  # MiniMax最大32768
        }

        # 获取当前提供商的限制
        provider = self.llm_factory.get_provider()
        limit = provider_limits.get(provider, 4096)  # 默认4096

        # 限制在合理范围内
        clamped = min(requested_tokens, limit)

        if requested_tokens > limit:
            logger.warning(
                f"[BaseAgent] 请求的max_tokens({requested_tokens})超过{provider.value}限制({limit})，"
                f"已自动调整为{clamped}"
            )

        return clamped

    async def call_llm(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        json_mode: bool = False,
    ) -> str:
        """LLM调用接口"""
        if not self.llm_client:
            raise ValueError("LLM客户端未设置，无法执行任务")

        # 根据提供商限制max_tokens上限，避免超出API限制
        max_tokens = self._clamp_max_tokens(max_tokens)

        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            # 增加API调用计数
            self.api_calls += 1

            # 计算当前耗时
            current_duration_ms = 0
            if self.start_time:
                current_duration_ms = int(
                    (datetime.utcnow() - self.start_time).total_seconds() * 1000
                )

            # 发送状态更新
            if self.status_callback:
                await self.status_callback(
                    {
                        "agent_type": self.agent_type.value,
                        "api_calls": self.api_calls,
                        "tokens_used": self.tokens_used,
                        "current_subtask": self.current_subtask,
                        "output_content": self.output_content[:500],  # 限制输出长度
                        "duration_ms": current_duration_ms,
                    }
                )

            response = await self.llm_client.chat.completions.create(**kwargs)

            # 统计token使用
            if response.usage:
                self.tokens_used += response.usage.total_tokens

            content = response.choices[0].message.content

            # 【重要】验证响应内容不为空，这是JSON解析失败的主要原因
            if not content or not content.strip():
                raise ValueError(
                    f"LLM返回空响应，json_mode={json_mode}，max_tokens={max_tokens}，可能API超时或配置有问题"
                )

            # 更新输出内容
            self.output_content = content[:1000]  # 保留最近的输出

            # 计算更新后的耗时
            if self.start_time:
                current_duration_ms = int(
                    (datetime.utcnow() - self.start_time).total_seconds() * 1000
                )

            # 发送状态更新
            if self.status_callback:
                await self.status_callback(
                    {
                        "agent_type": self.agent_type.value,
                        "api_calls": self.api_calls,
                        "tokens_used": self.tokens_used,
                        "current_subtask": self.current_subtask,
                        "output_content": self.output_content[:500],
                        "duration_ms": current_duration_ms,
                    }
                )

            logger.debug(f"[{self.name}] LLM响应: {content[:200]}...")

            return content

        except Exception as e:
            logger.error(f"[{self.name}] LLM调用失败: {e}")
            raise

    def get_metrics(self) -> dict:
        """获取执行指标"""
        duration = 0
        if self.start_time and self.end_time:
            duration = int((self.end_time - self.start_time).total_seconds() * 1000)

        return {
            "agent_type": self.agent_type.value,
            "name": self.name,
            "duration_ms": duration,
            "tokens_used": self.tokens_used,
        }

    def _start_timer(self):
        """开始计时"""
        self.start_time = datetime.utcnow()
        self.tokens_used = 0

    def _stop_timer(self):
        """停止计时"""
        self.end_time = datetime.utcnow()

    def _create_result(
        self,
        success: bool,
        output: Dict[str, Any],
        errors: List[str] = None,
        context_changes: Dict[str, Any] = None,
    ) -> AgentExecutionResult:
        """创建执行结果对象"""
        metrics = self.get_metrics()
        return AgentExecutionResult(
            agent_type=self.agent_type.value,
            success=success,
            output=output,
            errors=errors or [],
            tokens_used=metrics["tokens_used"],
            duration_ms=metrics["duration_ms"],
            context_changes=context_changes or {},
        )

    def _build_system_prompt(
        self, role_description: str, context: Dict[str, Any]
    ) -> str:
        """构建系统提示词"""
        core = context.get("core_context", {})
        extended = context.get("extended_context", {})
        kg_summary = context.get("knowledge_graph_summary", {})

        system_prompt = f"""{role_description}

## 当前研究任务
研究问题：{core.get("query", "")}

## 研究计划
{json.dumps(core.get("research_plan", []), ensure_ascii=False, indent=2)}

## 已验证的事实
{json.dumps(core.get("verified_facts", [])[:10], ensure_ascii=False, indent=2)}

## 关键实体
{", ".join(core.get("key_entities", [])[:20])}

## 知识图谱摘要
- 已验证事实数量: {kg_summary.get("verified_count", 0)}
- 高置信度节点数量: {kg_summary.get("high_confidence_count", 0)}
- 关键洞察: {json.dumps(kg_summary.get("key_insights", []), ensure_ascii=False)}

## 工作要求
1. 基于已有的上下文信息开展工作
2. 产出的结论必须有来源支撑
3. 如有新发现，需要明确标注置信度
"""
        return system_prompt
