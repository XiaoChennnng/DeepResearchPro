"""
Citer Agent - 引用管理Agent
负责为报告添加规范的引用和参考文献
"""

from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class CiterAgent(BaseAgent):
    """
    引用Agent
    为报告添加规范的引用标注，确保结论有来源依据
    """

    ROLE_DESCRIPTION = """你是一个专业的学术引用管理专家。你的职责是：
1. 为报告中的关键论述添加引用标注
2. 生成规范的参考文献列表
3. 验证引用与来源的一致性
4. 确保引用格式统一规范

引用标准（默认采用数字编号制，参考 GB/T 7714 等学术标准）：
- 文中使用数字中括号形式 [1]、[2]、[3] 标注引用
- 关键数据、事实、观点必须标注来源
- 参考文献按实际引用顺序编号排列
- 文献条目尽量包含作者、年份、标题、来源（期刊/会议/网站）等信息
- 在缺乏作者或年份信息时，不得凭空编造，只能使用已有元数据"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.CITER,
            name="引用标注Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行引用管理
        小陈说：给报告加上规范的引用，让它看起来更专业
        """
        self._start_timer()
        logger.info(f"[CiterAgent] 开始处理引用")

        try:
            core_context = context.get("core_context", {})
            extended_context = context.get("extended_context", {})
            sources = extended_context.get("source_references", [])
            working_data = extended_context.get("working_data", {})
            report = working_data.get("report", "")

            if not report:
                logger.warning("[CiterAgent] 没有报告可处理")
                self._stop_timer()
                return self._create_result(
                    success=True,
                    output={"cited_report": "", "citations": []},
                    context_changes={},
                )

            await self.update_subtask(f"正在为报告添加规范的引用标注")

            # 使用LLM添加引用
            cited_report, citations = await self._add_citations(report, sources)

            self._stop_timer()

            # 构建输出
            output = {
                "cited_report": cited_report,
                "citations": citations,
                "citations_count": len(citations),
                "knowledge_nodes": [
                    {
                        "type": "fact",
                        "content": f"报告已添加 {len(citations)} 条引用",
                        "confidence": 0.9,
                    }
                ],
            }

            # 上下文变更
            context_changes = {
                "extended": {
                    "working_data": {
                        "report": cited_report,
                        "citations": citations,
                        "citations_added_at": datetime.utcnow().isoformat(),
                    }
                }
            }

            logger.info(f"[CiterAgent] 引用处理完成，添加 {len(citations)} 条引用")

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"引用处理失败: {str(e)}"
            logger.error(f"[CiterAgent] {error_msg}")
            return self._create_result(
                success=False,
                output={
                    "cited_report": context.get("extended_context", {})
                    .get("working_data", {})
                    .get("report", "")
                },
                errors=[error_msg],
            )

    async def _add_citations(
        self, report: str, sources: List[Dict]
    ) -> tuple[str, List[Dict]]:
        """
        为报告添加引用
        小陈说：让AI给报告加上规范的引用标注
        """
        if not self.llm_client:
            return self._add_basic_citations(report, sources)

        # 构建来源列表
        sources_list = "\n".join(
            [
                f"[{i + 1}] 标题: {s.get('title', 'N/A')}\n    URL: {s.get('url', 'N/A')}\n    类型: {s.get('source_type', 'web')}\n    元数据: {json.dumps(s.get('source_metadata', {}), ensure_ascii=False)}\n    内容摘要: {s.get('content', 'N/A')[:200]}"
                for i, s in enumerate(sources[:30])
            ]
        )

        prompt = f"""你是一位学术引用规范专家。请为以下研究报告添加严格的引用标注。

## 可用的引用来源（共{len(sources[:30])}条）：
{sources_list}

## 原始报告内容：
{report}

## 你的任务：

### 1. 识别需要引用的内容
在报告中找出以下类型的内容，它们必须添加引用标注：
- 具体的数据、数字、统计结果
- 引用的观点、理论、研究结论
- 事实性陈述（如某公司做了什么、某政策规定了什么）
- 行业趋势、市场分析
- 专业术语的定义或解释

### 2. 添加引用标注格式
- 使用 [数字] 格式，如 [1]、[2]、[3]
- 引用标注放在相关句子或段落的末尾，标点符号之前
- 例如："电动汽车销量增长了30%[1]。" 或 "根据最新研究[2][3]，..."
- 如果一个论述需要多个来源支撑，使用 [1][2] 或 [1-3] 格式
- 确保引用编号从1开始连续编号

### 3. 引用数量要求
- 关键数据和核心论点必须有引用
- 每个主要章节至少应有2-5个引用
- 总引用数量应与来源数量相匹配（不低于来源数的50%）
- 不要过度引用导致影响可读性

返回JSON格式（务必确保JSON格式正确）：
{{
    "cited_report": "添加引用标注后的完整报告内容（保持原有Markdown格式，在适当位置插入[1][2]等引用标记）",
    "citations_mapping": [
        {{
            "citation_number": 1,
            "source_index": 0,
            "cited_text": "被引用的原文片段",
            "reason": "为什么需要引用这个来源"
        }},
        ...
    ],
    "total_citations": "插入的引用标记总数"
}}

## 重要提醒：
1. cited_report 必须是完整的报告，包含所有原始内容
2. 引用标记 [1][2] 等必须实际出现在 cited_report 的正文中
3. 不要只在参考文献部分列出来源，正文中也必须有对应的引用标记
4. 保持报告的原有结构、标题层级和Markdown格式
5. 不得编造不存在的信息"""

        try:
            # 计算足够的max_tokens以支持完整报告处理
            # citer需要处理完整报告并生成带引用的版本
            # 但注意不能超过provider的总限制
            estimated_output_tokens = max(8192, int(len(report) * 1.2))
            max_tokens = min(estimated_output_tokens, 40000)  # 安全边界

            logger.info(
                f"[CiterAgent] 添加引用，报告长度: {len(report)} 字符，max_tokens: {max_tokens}"
            )

            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens,
                json_mode=True,
            )

            result = json.loads(response)
            cited_report = result.get("cited_report", report)
            citations_mapping = result.get("citations_mapping", [])

            # 验证引用标记是否真的被添加到报告中
            citation_pattern = r"\[\d+\]"
            citations_in_report = re.findall(citation_pattern, cited_report)

            if len(citations_in_report) < 3:
                # 如果引用太少，说明LLM可能没有正确处理，尝试手动添加
                logger.warning(
                    f"[CiterAgent] LLM添加的引用数量不足({len(citations_in_report)}个)，尝试手动补充"
                )
                cited_report = self._ensure_citations_in_report(cited_report, sources)
                # 重新统计
                citations_in_report = re.findall(citation_pattern, cited_report)

            logger.info(
                f"[CiterAgent] 报告中包含 {len(citations_in_report)} 个引用标记"
            )

            # 生成参考文献列表
            reference_section = self._generate_references_section(
                sources, citations_mapping
            )

            # 如果报告没有参考文献部分，添加上
            if "## 参考文献" not in cited_report and "## 参考来源" not in cited_report:
                cited_report = cited_report.rstrip() + "\n\n" + reference_section

            return cited_report, citations_mapping

        except Exception as e:
            logger.error(f"[CiterAgent] LLM添加引用失败: {e}")
            return self._add_basic_citations(report, sources)

    def _ensure_citations_in_report(self, report: str, sources: List[Dict]) -> str:
        """
        确保报告中有引用标记
        小陈说：如果LLM没加好引用，小陈我来手动补上
        """
        # 检查是否已有足够的引用
        existing_citations = re.findall(r"\[\d+\]", report)
        if len(existing_citations) >= 5:
            return report

        # 找出报告中的关键段落，为它们添加引用
        lines = report.split("\n")
        modified_lines = []
        citation_counter = 1
        max_citations = min(len(sources), 15)  # 最多添加15个引用

        # 关键词模式：识别需要引用的内容
        data_patterns = [
            r"(\d+(?:\.\d+)?%)",  # 百分比
            r"(\d+(?:\.\d+)?亿)",  # 亿元
            r"(\d+(?:\.\d+)?万)",  # 万
            r"(增长|下降|上升|减少).*?(\d+)",  # 增长/下降描述
            r"(研究表明|数据显示|报告指出|调查发现|分析表明)",  # 研究引导词
            r"(根据.*?统计|据.*?报道|来自.*?的数据)",  # 来源引导词
        ]

        for line in lines:
            # 跳过标题行和已有引用的行
            if line.startswith("#") or re.search(r"\[\d+\]", line):
                modified_lines.append(line)
                continue

            # 跳过空行和很短的行
            if len(line.strip()) < 20:
                modified_lines.append(line)
                continue

            # 检查是否包含需要引用的内容
            needs_citation = False
            for pattern in data_patterns:
                if re.search(pattern, line):
                    needs_citation = True
                    break

            if needs_citation and citation_counter <= max_citations:
                # 在句子末尾添加引用（在句号之前）
                if line.rstrip().endswith("。"):
                    line = line.rstrip()[:-1] + f"[{citation_counter}]。"
                elif line.rstrip().endswith("."):
                    line = line.rstrip()[:-1] + f"[{citation_counter}]."
                elif line.rstrip().endswith("；") or line.rstrip().endswith(";"):
                    line = line.rstrip()[:-1] + f"[{citation_counter}]；"
                else:
                    # 如果没有标点，直接在末尾添加
                    line = line.rstrip() + f"[{citation_counter}]"
                citation_counter += 1

            modified_lines.append(line)

        return "\n".join(modified_lines)

    def _add_basic_citations(
        self, report: str, sources: List[Dict]
    ) -> tuple[str, List[Dict]]:
        """
        基础引用处理（无LLM时使用）
        小陈说：没有AI也得能干活，手动添加引用标记
        """
        # 先尝试手动添加引用标记
        cited_report = self._ensure_citations_in_report(report, sources)

        # 生成参考文献列表
        reference_section = self._generate_references_section(sources, [])

        # 如果报告没有参考文献部分，添加上
        if "## 参考文献" not in cited_report and "## 参考来源" not in cited_report:
            cited_report = cited_report.rstrip() + "\n\n" + reference_section

        # 统计添加的引用数量
        citations_count = len(re.findall(r"\[\d+\]", cited_report))
        logger.info(f"[CiterAgent] 基础模式添加了 {citations_count} 个引用标记")

        return cited_report, []

    def _generate_references_section(
        self, sources: List[Dict], citations_mapping: List[Dict]
    ) -> str:
        """
        生成参考文献部分
        小陈说：按照学术规范生成参考文献列表
        """
        cited_indices = set()
        for citation in citations_mapping:
            idx = citation.get("source_index")
            if isinstance(idx, int) and idx >= 0:
                cited_indices.add(idx)

        if not cited_indices:
            cited_indices = set(range(min(len(sources), 20)))

        references: List[str] = []

        def normalize_whitespace(text: str) -> str:
            text = text or ""
            return re.sub(r"\s+", " ", text.strip())

        for i, source in enumerate(sources):
            if i not in cited_indices and i >= 20:
                continue

            title_raw = source.get("title", "未知标题")
            title = normalize_whitespace(title_raw)
            url = (source.get("url") or "").strip()
            source_type = (source.get("source_type") or "web").lower()
            metadata = source.get("source_metadata") or {}

            authors = metadata.get("authors") or metadata.get("author") or ""
            if isinstance(authors, list):
                authors_str = ", ".join(
                    [normalize_whitespace(str(a)) for a in authors if str(a).strip()]
                )
            else:
                authors_str = normalize_whitespace(str(authors)) if authors else "佚名"

            year = metadata.get("year") or metadata.get("date") or ""
            year_str = normalize_whitespace(str(year)) if year else ""

            journal = (
                normalize_whitespace(str(metadata.get("journal", "")))
                if metadata.get("journal")
                else ""
            )
            publisher = (
                normalize_whitespace(str(metadata.get("publisher", "")))
                if metadata.get("publisher")
                else ""
            )
            volume = (
                normalize_whitespace(str(metadata.get("volume", "")))
                if metadata.get("volume")
                else ""
            )
            issue = (
                normalize_whitespace(str(metadata.get("issue", "")))
                if metadata.get("issue")
                else ""
            )
            pages = (
                normalize_whitespace(str(metadata.get("pages", "")))
                if metadata.get("pages")
                else ""
            )
            doi = (
                normalize_whitespace(str(metadata.get("doi", "")))
                if metadata.get("doi")
                else ""
            )

            idx_num = len(references) + 1

            if journal:
                entry = f"[{idx_num}] {authors_str}. {title}[J]. {journal}"
                if year_str:
                    entry += f", {year_str}"
                if volume or issue:
                    vol_issue = volume
                    if issue:
                        vol_issue = (
                            f"{vol_issue}({issue})" if vol_issue else f"({issue})"
                        )
                    if vol_issue:
                        entry += f", {vol_issue}"
                if pages:
                    entry += f": {pages}"
                if doi:
                    entry += f". DOI: {doi}"
                if url:
                    entry += f". {url}"
            elif publisher:
                entry = f"[{idx_num}] {authors_str}. {title}[M]. {publisher}"
                if year_str:
                    entry += f", {year_str}"
                if pages:
                    entry += f": {pages}"
                if url:
                    entry += f". {url}"
            else:
                entry = f"[{idx_num}] {authors_str}. {title}[EB/OL]"
                if year_str:
                    entry += f". {year_str}"
                if url:
                    entry += f". {url}"

            references.append(entry)

        references_text = "\n".join(references)

        return f"""## 参考文献

{references_text}
"""
