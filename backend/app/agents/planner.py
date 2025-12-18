"""
Planner Agent - 研究规划Agent
负责将研究问题拆解为详细的可执行研究计划
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from app.agents.base import BaseAgent, AgentState
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult
from app.api.endpoints.websocket import get_ws_manager


class PlannerAgent(BaseAgent):
    """
    规划Agent
    将用户的研究问题拆解为可执行的研究计划
    """

    ROLE_DESCRIPTION = """你是一个专业的研究规划专家。你的职责是：
1. 深入理解用户的研究问题
2. 将复杂问题拆解为可执行的研究步骤
3. 为每个步骤定义清晰的目标和预期产出
4. 识别研究的关键实体和约束条件

你必须产出结构化的研究计划，确保计划可执行且全面覆盖研究问题的各个方面。"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.PLANNER,
            name="研究规划Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行研究规划任务
        将研究问题拆解为详细的可执行计划
        """
        self._start_timer()
        logger.info(f"[PlannerAgent] 开始规划研究任务")

        try:
            query = context.get("core_context", {}).get("query", "")
            if not query:
                raise ValueError("研究问题为空，无法制定研究计划")

            # 更新子任务
            await self.update_subtask(f"正在分析研究问题：{query[:50]}...")

            # 构建系统提示词
            system_prompt = self._build_system_prompt(self.ROLE_DESCRIPTION, context)

            await self.update_subtask("正在制定详细的研究计划")

            # 构建用户提示词
            user_prompt = f"""请为以下研究问题制定详细的研究计划：

研究问题：{query}

请以JSON格式返回研究计划，格式如下：
{{
    "research_objective": "研究目标的一句话概述",
    "key_entities": ["关键实体1", "关键实体2", ...],
    "constraints": ["约束条件1", "约束条件2", ...],
    "plan": [
        {{
            "step": 1,
            "title": "步骤标题",
            "description": "详细描述",
            "search_queries": ["搜索查询1", "搜索查询2"],
            "expected_output": "预期产出"
        }},
        ...
    ],
    "estimated_sources_needed": 10,
    "research_depth": "comprehensive/moderate/quick"
}}

要求：
1. 计划必须全面覆盖研究问题的各个方面
2. 每个步骤必须有明确的目标和预期产出
3. 搜索查询必须精准且多样化
4. 识别所有关键实体（人物、组织、概念、技术等）
5. 列出所有约束条件（时间范围、地域限制、数据来源等）"""

            # 调用LLM
            response = await self.call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=8192,
                json_mode=True,
            )

            # 解析响应：尽量容错，确保即使LLM格式不标准也能产出研究计划
            try:
                # 有些模型在json_mode下可能直接返回dict，这里做一层兼容
                if isinstance(response, dict):
                    plan_data = response
                elif isinstance(response, list):
                    plan_data = {"plan": response}
                else:
                    plan_data = json.loads(response)
            except Exception as e:
                logger.error(f"[PlannerAgent] LLM返回的JSON解析失败: {e}")
                import re

                if isinstance(response, str):
                    json_match = re.search(r"\{[\s\S]*\}", response)
                    if json_match:
                        try:
                            plan_data = json.loads(json_match.group())
                        except Exception as e2:
                            logger.error(f"[PlannerAgent] 再次解析JSON失败: {e2}")
                            plan_data = self._build_fallback_plan(query, response)
                    else:
                        logger.warning(
                            "[PlannerAgent] 无法从LLM响应中提取JSON，使用降级规划方案"
                        )
                        plan_data = self._build_fallback_plan(query, response)
                else:
                    logger.warning("[PlannerAgent] LLM响应类型异常，使用降级规划方案")
                    plan_data = self._build_fallback_plan(query, str(response))

            self._stop_timer()

            # 构建输出
            output = {
                "plan": plan_data.get("plan", []),
                "research_objective": plan_data.get("research_objective", ""),
                "key_entities": plan_data.get("key_entities", []),
                "constraints": plan_data.get("constraints", []),
                "estimated_sources_needed": plan_data.get(
                    "estimated_sources_needed", 10
                ),
                "research_depth": plan_data.get("research_depth", "moderate"),
                "knowledge_nodes": [
                    {
                        "type": "insight",
                        "content": f"研究目标: {plan_data.get('research_objective', '')}",
                        "confidence": 0.9,
                    }
                ],
            }

            # 上下文变更
            context_changes = {
                "core": {
                    "research_plan": plan_data.get("plan", []),
                    "key_entities": plan_data.get("key_entities", []),
                    "constraints": plan_data.get("constraints", []),
                },
                "extended": {
                    "working_data": {
                        "research_objective": plan_data.get("research_objective", ""),
                        "estimated_sources_needed": plan_data.get(
                            "estimated_sources_needed", 10
                        ),
                        "research_depth": plan_data.get("research_depth", "moderate"),
                    }
                },
            }

            # 通过WebSocket推送规划结果快照，便于前端实时显示研究计划
            try:
                core_ctx = context.get("core_context", {}) or {}
                task_id = core_ctx.get("task_id")
                if task_id:
                    ws_manager = get_ws_manager()
                    await ws_manager.broadcast_to_task(
                        task_id,
                        {
                            "type": "plan_snapshot",
                            "task_id": task_id,
                            "plan": plan_data.get("plan", []),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
            except Exception as e:
                logger.error(f"[PlannerAgent] 发送plan_snapshot失败: {e}")

            logger.info(f"[PlannerAgent] 规划完成，共 {len(output['plan'])} 个步骤")

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"规划失败: {str(e)}"
            logger.error(f"[PlannerAgent] {error_msg}")

            if "研究问题为空" in error_msg:
                return self._create_result(success=False, output={}, errors=[error_msg])

            plan_data = self._build_fallback_plan(query or "", str(e))

            output = {
                "plan": plan_data.get("plan", []),
                "research_objective": plan_data.get("research_objective", ""),
                "key_entities": plan_data.get("key_entities", []),
                "constraints": plan_data.get("constraints", []),
                "estimated_sources_needed": plan_data.get(
                    "estimated_sources_needed", 10
                ),
                "research_depth": plan_data.get("research_depth", "moderate"),
                "knowledge_nodes": [
                    {
                        "type": "insight",
                        "content": f"研究目标: {plan_data.get('research_objective', '')}",
                        "confidence": 0.9,
                    }
                ],
            }

            context_changes = {
                "core": {
                    "research_plan": plan_data.get("plan", []),
                    "key_entities": plan_data.get("key_entities", []),
                    "constraints": plan_data.get("constraints", []),
                },
                "extended": {
                    "working_data": {
                        "research_objective": plan_data.get("research_objective", ""),
                        "estimated_sources_needed": plan_data.get(
                            "estimated_sources_needed", 10
                        ),
                        "research_depth": plan_data.get("research_depth", "moderate"),
                    }
                },
            }

            try:
                core_ctx = context.get("core_context", {}) or {}
                task_id = core_ctx.get("task_id")
                if task_id:
                    ws_manager = get_ws_manager()
                    await ws_manager.broadcast_to_task(
                        task_id,
                        {
                            "type": "plan_snapshot",
                            "task_id": task_id,
                            "plan": plan_data.get("plan", []),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
            except Exception as ws_error:
                logger.error(f"[PlannerAgent] 发送降级plan_snapshot失败: {ws_error}")

            logger.info(
                f"[PlannerAgent] 使用降级方案完成规划，共 {len(output['plan'])} 个步骤"
            )

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

    def _build_fallback_plan(self, query: str, raw_response: str) -> Dict[str, Any]:
        title = query.strip() or "研究主题"
        steps: List[Dict[str, Any]] = []

        base_steps = [
            (1, "理解研究问题和背景"),
            (2, "收集相关资料和数据"),
            (3, "整理和筛选关键信息"),
            (4, "分析数据并形成结论"),
            (5, "撰写研究报告并检查引用"),
        ]

        for step, step_title in base_steps:
            steps.append(
                {
                    "step": step,
                    "title": step_title,
                    "description": f"围绕『{title}』执行：{step_title}",
                    "search_queries": [],
                    "expected_output": "",
                }
            )

        return {
            "research_objective": title[:80],
            "key_entities": [],
            "constraints": [],
            "plan": steps,
            "estimated_sources_needed": 10,
            "research_depth": "moderate",
        }
