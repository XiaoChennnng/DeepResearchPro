"""
Analyzer Agent - 深度分析Agent
负责分析收集的信息，提取有价值的洞察和结论
"""

from typing import Dict, Any, List, Optional
import json
from datetime import datetime

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class AnalyzerAgent(BaseAgent):
    """
    分析Agent
    深度分析收集的信息，提取有价值的洞察
    """

    # 分析框架
    ANALYSIS_FRAMEWORKS = {
        "PESTEL": "政治、经济、社会、技术、环境、法律分析框架",
        "SWOT": "优势、劣势、机遇、威胁分析框架",
        "5W2H": "何人、何事、何时、何地、何因、如何、何价分析框架",
        "LogicTree": "逻辑树分解分析框架",
        "Fishbone": "鱼骨图因果分析框架",
        "CausalChain": "因果链分析框架",
        "SystemsThinking": "系统思维分析框架",
    }

    ROLE_DESCRIPTION = """你是一个专业的数据分析专家和批判性思考者。你的职责是：
1. 深度分析收集的信息来源，使用专业的分析框架
2. 识别关键趋势、模式和洞察，进行批判性评估
3. 提取并验证关键事实，建立因果关系
4. 建立信息之间的关联，识别矛盾和空白
5. 评估信息的可靠性和重要性，进行不确定性分析

你必须基于证据进行分析，每个结论都要有来源支撑，并考虑替代解释。
分析方法：
- 交叉验证：通过多个来源验证事实，识别一致性和矛盾
- 因果分析：建立因果链，区分相关性和因果性
- 批判性思维：识别假设前提，考虑反例和边界条件
- 系统思维：分析要素间的相互作用和反馈循环
- 不确定性评估：量化分析结论的置信度和适用范围"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.ANALYZER,
            name="信息分析Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行深度分析
        小陈说：把收集的信息分析透彻，提取有价值的洞察
        """
        self._start_timer()
        logger.info(f"[AnalyzerAgent] 开始深度分析")

        try:
            core_context = context.get("core_context", {})
            extended_context = context.get("extended_context", {})
            query = core_context.get("query", "")
            sources = extended_context.get("source_references", [])

            if not sources:
                logger.warning("[AnalyzerAgent] 没有来源可分析")
                self._stop_timer()
                return self._create_result(
                    success=True,
                    output={"analysis": {}, "insights": []},
                    context_changes={},
                )

            logger.info(f"[AnalyzerAgent] 待分析来源数量: {len(sources)}")

            await self.update_subtask(
                f"正在深度分析 {len(sources)} 个信息来源，提取关键洞察"
            )

            # 使用LLM进行深度分析
            analysis_result = await self._analyze_sources(sources, query, core_context)

            self._stop_timer()

            # 构建知识节点
            knowledge_nodes = []
            for insight in analysis_result.get("insights", []):
                knowledge_nodes.append(
                    {
                        "type": "insight",
                        "content": insight.get("content", ""),
                        "confidence": insight.get("confidence", 0.5),
                        "source_ids": insight.get("source_indices", []),
                    }
                )

            for fact in analysis_result.get("key_facts", []):
                knowledge_nodes.append(
                    {
                        "type": "fact",
                        "content": fact.get("content", ""),
                        "confidence": fact.get("confidence", 0.7),
                        "source_ids": fact.get("source_indices", []),
                    }
                )

            # 构建输出
            output = {
                "analysis": analysis_result,
                "insights": analysis_result.get("insights", []),
                "key_facts": analysis_result.get("key_facts", []),
                "trends": analysis_result.get("trends", []),
                "summary": analysis_result.get("summary", ""),
                "knowledge_nodes": knowledge_nodes,
            }

            # 上下文变更
            context_changes = {
                "extended": {
                    "intermediate_results": [analysis_result],
                    "working_data": {
                        "analysis_summary": analysis_result.get("summary", ""),
                        "insights_count": len(analysis_result.get("insights", [])),
                        "key_facts_count": len(analysis_result.get("key_facts", [])),
                    },
                }
            }

            logger.info(
                f"[AnalyzerAgent] 分析完成，提取 {len(output['insights'])} 个洞察"
            )

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"分析失败: {str(e)}"
            logger.error(f"[AnalyzerAgent] {error_msg}")
            return self._create_result(
                success=False, output={"analysis": {}}, errors=[error_msg]
            )

    def _select_analysis_framework(self, query: str, sources: List[Dict]) -> str:
        """
        根据研究问题和可用数据选择最合适的分析框架
        """
        # 基于问题类型自动选择框架
        query_lower = query.lower()

        if any(keyword in query_lower for keyword in ["政策", "政府", "法规", "政治"]):
            return "PESTEL"
        elif any(
            keyword in query_lower
            for keyword in ["优势", "劣势", "机会", "威胁", "竞争力"]
        ):
            return "SWOT"
        elif any(
            keyword in query_lower for keyword in ["原因", "为什么", "因果", "机制"]
        ):
            return "CausalChain"
        elif any(
            keyword in query_lower for keyword in ["系统", "复杂", "相互作用", "反馈"]
        ):
            return "SystemsThinking"
        elif any(
            keyword in query_lower for keyword in ["问题", "改进", "解决", "步骤"]
        ):
            return "5W2H"
        else:
            # 默认使用逻辑树分析
            return "LogicTree"

    async def _analyze_sources(
        self, sources: List[Dict], query: str, core_context: Dict
    ) -> Dict[str, Any]:
        """
        使用LLM深度分析来源
        小陈说：把所有来源喂给AI，让它分析出有价值的东西
        """
        if not self.llm_client:
            return self._simple_analysis(sources)

        # 选择合适的分析框架
        selected_framework = self._select_analysis_framework(query, sources)

        # 构建来源描述（增加内容长度）
        sources_text = "\n\n".join(
            [
                f"来源 {i + 1}:\n"
                f"标题: {s.get('title', 'N/A')}\n"
                f"内容: {s.get('content', 'N/A')[:1200]}\n"  # 从800增加到1200
                f"可信度: {s.get('confidence', 'unknown')}\n"
                f"关键信息: {s.get('key_information', '')}"
                for i, s in enumerate(sources[:20])  # 从15增加到20个来源
            ]
        )

        prompt = f"""请对以下研究资料进行深度分析，提取高价值的关键洞察和可验证的事实。

研究问题：{query}

关键实体：{", ".join(core_context.get("key_entities", [])[:10])}

研究资料：
{sources_text}

=== 分析框架 ===
本次分析将使用 {self.ANALYSIS_FRAMEWORKS[selected_framework]} 框架。
请在分析过程中明确应用此框架的各个要素。

=== 深度分析要求 ===
1. **理论框架构建**：明确分析的理论基础和概念框架
2. **因果分析**：建立清晰的因果链，区分相关性和因果性
3. **批判性思维**：识别假设前提，考虑反例和替代解释
4. **不确定性评估**：量化结论的置信度和适用边界
5. **系统思维**：分析要素间的相互作用和反馈机制

=== 推理过程记录 ===
对每个重要结论，请记录推理过程：
- 前提假设
- 推理步骤
- 证据支撑
- 替代解释
- 不确定性来源

你的目标是以"博士论文级别"的严谨程度完成分析，
读者假定为顶级学术会议/SSCI/SCI 期刊的评审专家，
分析需要体现清晰的理论框架、证据链和反驳讨论。

请严格按照下述结构返回 JSON 格式的分析结果（必须是合法 JSON）：
{{
    "summary": "整体分析摘要（200-300字）",
    "key_facts": [
        {{
            "content": "关键事实描述",
            "confidence": 0.9,
            "source_indices": [1, 3],
            "category": "定义/数据/事件/关系"
        }},
        ...
    ],
    "insights": [
        {{
            "type": "trend/pattern/correlation/anomaly/causal_relationship/systemic_insight",
            "content": "洞察描述",
            "confidence": 0.8,
            "source_indices": [1, 2],
            "importance": "high/medium/low",
            "reasoning_chain": {{
                "assumptions": ["前提假设1", "前提假设2"],
                "evidence": "支撑证据的详细说明",
                "alternative_explanations": ["替代解释1", "替代解释2"],
                "uncertainty_factors": ["不确定性来源1"],
                "boundary_conditions": "结论的适用边界"
            }},
            "framework_application": "如何应用{selected_framework}框架的具体说明"
        }},
        ...
    ],
    "trends": [
        {{
            "description": "趋势描述",
            "direction": "up/down/stable",
            "time_range": "时间范围",
            "evidence": "支撑证据"
        }},
        ...
    ],
    "data_quality_assessment": {{
        "overall_reliability": "high/medium/low",
        "coverage": "comprehensive/partial/limited",
        "consistency": "consistent/mixed/contradictory",
        "gaps": ["信息空白1", "信息空白2"]
    }},
    "contradictions": [
        {{
            "description": "矛盾描述",
            "source_indices": [1, 5],
            "resolution": "可能的解释"
        }}
    ]
}}

分析要求：
1. 每个事实和洞察必须标注来源索引，并给出简短证据说明
2. 置信度基于来源质量和交叉验证程度，避免凭空猜测
3. 识别来源之间的矛盾并尝试解释，必要时给出多种可能解释
4. 评估数据质量，指出信息空白和样本偏差
5. 对每一个核心结论，明确其理论依据和适用边界
6. 指出当前证据无法回答的问题，并提出2-3个后续研究方向
7. 如果资料本身不足以支持强结论，要明确标注为“不确定/需谨慎”而不是下结论"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,  # 从0.3提升到0.7，增加创造性和深度思考
                max_tokens=10000,  # 从8192提升到10000，支持更深入的分析
                json_mode=True,
            )

            result = json.loads(response)
            return result

        except Exception as e:
            logger.error(f"[AnalyzerAgent] LLM分析失败: {e}")
            return self._simple_analysis(sources)

    def _simple_analysis(self, sources: List[Dict]) -> Dict[str, Any]:
        """
        简单分析（无LLM时使用）
        小陈说：没有AI也得能干活，用规则先顶着
        """
        # 统计来源质量
        high_confidence = len([s for s in sources if s.get("confidence") == "high"])
        medium_confidence = len([s for s in sources if s.get("confidence") == "medium"])
        low_confidence = len([s for s in sources if s.get("confidence") == "low"])

        # 提取关键信息
        key_facts = []
        for i, source in enumerate(sources[:10]):
            key_info = source.get("key_information", "")
            if key_info:
                key_facts.append(
                    {
                        "content": key_info,
                        "confidence": 0.6,
                        "source_indices": [i + 1],
                        "category": "信息",
                    }
                )

        return {
            "summary": f"基于 {len(sources)} 个来源的分析摘要",
            "key_facts": key_facts,
            "insights": [],
            "trends": [],
            "data_quality_assessment": {
                "overall_reliability": "medium"
                if high_confidence > len(sources) * 0.3
                else "low",
                "coverage": "partial",
                "consistency": "unknown",
                "gaps": ["需要LLM进行深度分析"],
            },
            "contradictions": [],
        }
