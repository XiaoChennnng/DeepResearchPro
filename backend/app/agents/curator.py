"""
Curator Agent - 信息筛选Agent
负责筛选和整理搜索到的信息，保留高质量内容
"""

from typing import Dict, Any, List, Optional
import json

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class CuratorAgent(BaseAgent):
    """
    筛选Agent
    负责筛选搜索结果，保留有价值的信息
    """

    ROLE_DESCRIPTION = """你是一个专业的信息筛选专家。你的职责是：
1. 评估信息来源的可信度和权威性
2. 判断信息与研究问题的相关性
3. 识别重复、过时或错误的信息
4. 提取和整理高质量的信息片段
5. 建立信息之间的关联

你必须严格筛选信息，确保只有高质量、相关的信息进入后续分析阶段。
质量要求：
- 可信度：优先选择权威来源（学术期刊、官方网站、知名媒体）
- 时效性：优先选择最新的信息
- 完整性：信息应该足够完整，能够支撑分析
- 多样性：保持信息来源的多样性，避免偏见"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.CURATOR,
            name="信息筛选Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行信息筛选
        小陈说：把搜索到的信息筛选一遍，垃圾的扔掉，好的留下
        """
        self._start_timer()
        logger.info(f"[CuratorAgent] 开始筛选信息")

        try:
            core_context = context.get("core_context", {})
            extended_context = context.get("extended_context", {})
            query = core_context.get("query", "")
            sources = extended_context.get("source_references", [])

            if not sources:
                logger.warning("[CuratorAgent] 没有来源可筛选")
                self._stop_timer()
                return self._create_result(
                    success=True,
                    output={"curated_sources": [], "rejected_count": 0},
                    context_changes={},
                )

            logger.info(f"[CuratorAgent] 待筛选来源数量: {len(sources)}")

            await self.update_subtask(
                f"正在筛选 {len(sources)} 个信息来源，评估质量和相关性"
            )

            # 使用LLM进行筛选
            (
                curated_sources,
                rejected_count,
                curation_notes,
            ) = await self._curate_sources(sources, query, core_context)

            self._stop_timer()

            # 构建输出
            output = {
                "curated_sources": curated_sources,
                "total_input": len(sources),
                "total_curated": len(curated_sources),
                "rejected_count": rejected_count,
                "curation_notes": curation_notes,
                "knowledge_nodes": [
                    {
                        "type": "fact",
                        "content": f"从 {len(sources)} 个来源中筛选出 {len(curated_sources)} 个高质量来源",
                        "confidence": 0.9,
                    }
                ],
            }

            # 上下文变更
            context_changes = {
                "extended": {
                    "source_references": curated_sources,
                    "working_data": {
                        "curation_notes": curation_notes,
                        "rejected_count": rejected_count,
                    },
                    "notes": [
                        f"筛选通过率: {len(curated_sources) / len(sources) * 100:.1f}%"
                    ],
                }
            }

            logger.info(
                f"[CuratorAgent] 筛选完成，保留 {len(curated_sources)}/{len(sources)} 个来源"
            )

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"筛选失败: {str(e)}"
            logger.error(f"[CuratorAgent] {error_msg}")
            return self._create_result(
                success=False, output={"curated_sources": []}, errors=[error_msg]
            )

    async def _curate_sources(
        self, sources: List[Dict], query: str, core_context: Dict
    ) -> tuple[List[Dict], int, List[str]]:
        """
        使用LLM筛选来源
        小陈说：用AI来判断哪些信息是有价值的
        """
        if not self.llm_client:
            # 没有LLM就用简单的规则筛选
            return self._simple_curation(sources)

        # 分批处理（每批最多10个）
        batch_size = 10
        all_curated = []
        all_notes = []
        total_rejected = 0

        for i in range(0, len(sources), batch_size):
            batch = sources[i : i + batch_size]
            curated, rejected, notes = await self._curate_batch(
                batch, query, core_context
            )
            all_curated.extend(curated)
            all_notes.extend(notes)
            total_rejected += rejected

        return all_curated, total_rejected, all_notes

    async def _curate_batch(
        self, sources: List[Dict], query: str, core_context: Dict
    ) -> tuple[List[Dict], int, List[str]]:
        """筛选一批来源"""
        # 构建来源描述
        sources_text = "\n\n".join(
            [
                f"来源 {i + 1}:\n"
                f"标题: {s.get('title', 'N/A')}\n"
                f"URL: {s.get('url', 'N/A')}\n"
                f"内容: {s.get('content', 'N/A')[:500]}\n"
                f"当前可信度: {s.get('confidence', 'unknown')}"
                for i, s in enumerate(sources)
            ]
        )

        # 构建提示词
        prompt = f"""请评估以下信息来源的质量，并决定是否保留。

研究问题：{query}

关键实体：{", ".join(core_context.get("key_entities", [])[:10])}

待评估来源：
{sources_text}

请以JSON格式返回评估结果：
{{
    "decisions": [
        {{
            "index": 1,
            "keep": true,
            "reason": "保留/拒绝的原因",
            "credibility_score": 0.8,
            "relevance_score": 0.9,
            "extracted_facts": ["提取的关键事实1", "提取的关键事实2"],
            "source_type_refined": "academic/news/official/blog/other"
        }},
        ...
    ],
    "overall_notes": ["整体筛选说明1", "整体筛选说明2"]
}}

筛选标准：
1. 高度相关性（与研究问题直接相关）
2. 可信来源（权威机构、学术期刊、官方网站）
3. 信息完整性（包含有价值的具体信息）
4. 时效性（优先保留最新信息）
5. 剔除广告、垃圾内容、明显错误信息"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=8192,
                json_mode=True,
            )

            result = json.loads(response)
            decisions = result.get("decisions", [])
            notes = result.get("overall_notes", [])

            curated = []
            rejected = 0

            for decision in decisions:
                idx = decision.get("index", 0) - 1
                if 0 <= idx < len(sources):
                    if decision.get("keep", False):
                        source = sources[idx].copy()
                        source["is_curated"] = True
                        source["credibility_score"] = decision.get(
                            "credibility_score", 0.5
                        )
                        source["relevance_score"] = decision.get("relevance_score", 0.5)
                        source["extracted_facts"] = decision.get("extracted_facts", [])
                        source["source_type"] = decision.get(
                            "source_type_refined", source.get("source_type", "web")
                        )
                        source["curation_reason"] = decision.get("reason", "")
                        curated.append(source)
                    else:
                        rejected += 1

            return curated, rejected, notes

        except Exception as e:
            logger.error(f"[CuratorAgent] 批量筛选失败: {e}")
            # 失败时保留所有来源
            for s in sources:
                s["is_curated"] = False
            return sources, 0, [f"筛选过程出错: {str(e)}"]

    def _simple_curation(
        self, sources: List[Dict]
    ) -> tuple[List[Dict], int, List[str]]:
        """
        简单规则筛选（无LLM时使用）
        小陈说：没有AI也得能干活，用规则先顶着
        """
        curated = []
        rejected = 0

        for source in sources:
            # 简单的启发式规则
            score = 0

            # 有标题加分
            if source.get("title"):
                score += 1

            # 有URL加分
            if source.get("url"):
                score += 1

            # 内容长度足够加分
            content = source.get("content", "")
            if len(content) > 100:
                score += 1
            if len(content) > 500:
                score += 1

            # 相关性分数高加分
            if source.get("relevance_score", 0) > 0.5:
                score += 2

            # 阈值判断
            if score >= 3:
                source["is_curated"] = True
                curated.append(source)
            else:
                rejected += 1

        return curated, rejected, ["使用简单规则筛选（无LLM）"]
