"""
Writer Agent - 报告写作Agent
"""

from typing import Dict, Any, List, Optional
import json
import re
from datetime import datetime

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class WriterAgent(BaseAgent):
    """写作Agent"""

    # 深度管理器
    class DepthManager:
        def __init__(self):
            self.depth_metrics = {
                "theory_depth": 0,
                "evidence_strength": 0,
                "critical_thinking": 0,
                "future_orientation": 0,
            }

        def assess_depth(self, content: str) -> Dict[str, float]:
            """评估内容深度"""
            return {
                "theory_depth": self._check_theory_building(content),
                "evidence_strength": self._check_evidence_quality(content),
                "critical_thinking": self._check_critical_analysis(content),
                "future_orientation": self._check_future_outlook(content),
            }

        def needs_deepening(self, scores: Dict[str, float]) -> bool:
            """判断是否需要深化"""
            return any(score < 0.7 for score in scores.values())

        def _check_theory_building(self, content: str) -> float:
            """检查理论构建深度"""
            theory_indicators = [
                "理论框架",
                "概念模型",
                "理论基础",
                "理论视角",
                "理论贡献",
                "理论意义",
                "理论创新",
            ]
            score = sum(1 for indicator in theory_indicators if indicator in content)
            return min(score / 3.0, 1.0)  # 至少需要3个理论要素

        def _check_evidence_quality(self, content: str) -> float:
            """检查证据质量"""
            evidence_indicators = [
                "数据表明",
                "研究显示",
                "证据显示",
                "实证研究",
                "多源验证",
                "交叉验证",
                "实证证据",
            ]
            score = sum(1 for indicator in evidence_indicators if indicator in content)
            return min(score / 2.0, 1.0)  # 至少需要2个证据要素

        def _check_critical_analysis(self, content: str) -> float:
            """检查批判性思维"""
            critical_indicators = [
                "然而",
                "但",
                "局限性",
                "不足",
                "问题",
                "挑战",
                "替代解释",
                "反例",
                "边界条件",
                "批判性分析",
            ]
            score = sum(1 for indicator in critical_indicators if indicator in content)
            return min(score / 3.0, 1.0)  # 至少需要3个批判性要素

        def _check_future_outlook(self, content: str) -> float:
            """检查未来展望"""
            future_indicators = [
                "未来趋势",
                "发展趋势",
                "预测",
                "展望",
                "研究方向",
                "机遇",
                "挑战",
                "对策建议",
            ]
            score = sum(1 for indicator in future_indicators if indicator in content)
            return min(score / 2.0, 1.0)  # 至少需要2个未来要素

    # 深度分析框架
    class DepthAnalysisFramework:
        THEORY_BUILDING = "构建理论框架：识别核心理论、建立概念模型、分析理论适用性"
        CAUSAL_ANALYSIS = "因果分析：识别驱动因素、分析机制、评估影响路径"
        CRITICAL_THINKING = "批判性思考：识别反例、评估局限性、探讨替代解释"
        FUTURE_OUTLOOK = "未来展望：预测趋势、识别机遇、提出对策建议"

        @classmethod
        def get_depth_requirements(cls, part_name: str) -> str:
            """根据部分名称返回深度要求"""
            requirements = {
                "abstract": f"{cls.THEORY_BUILDING}\n{cls.CAUSAL_ANALYSIS}\n重点：核心发现浓缩与理论定位",
                "introduction": f"{cls.THEORY_BUILDING}\n重点：问题深度剖析与研究价值论证",
                "literature": f"{cls.THEORY_BUILDING}\n{cls.CRITICAL_THINKING}\n重点：理论综述与批判性评估",
                "methodology": f"{cls.CRITICAL_THINKING}\n重点：方法论创新与局限性分析",
                "findings": f"{cls.CAUSAL_ANALYSIS}\n重点：实证证据与机制深度解释",
                "discussion": f"{cls.CRITICAL_THINKING}\n{cls.FUTURE_OUTLOOK}\n重点：理论贡献挖掘与应用价值拓展",
                "conclusion": f"{cls.FUTURE_OUTLOOK}\n重点：研究成果总结与未来方向展望",
            }
            return requirements.get(part_name, "")

    # AI高频用语禁用词库（精简版，只保留最明显的AI痕迹）
    AI_BANNED_PHRASES = [
        # 只保留最明显的AI痕迹用词，避免过度限制表达
        "值得注意的是",
        "需要注意的是",
        "总的来说",
        "综上所述",
        "在当今社会",
        "随着科技的发展",
        "众所周知",
        "毋庸置疑",
        "显而易见",
        "首先",
        "其次",
        "最后",
        "总之",
        "一方面",
        "另一方面",
        "与此同时",
        "不可否认",
        "无可厚非",
        "由此可见",
        "换句话说",
        "换言之",
        "也就是说",
        "事实上",
        "实际上",
        "客观来说",
        "从某种程度上说",
        "在一定程度上",
        "具有重要意义",
        "具有深远影响",
        "发挥着重要作用",
        "得到了广泛关注",
        "引起了广泛讨论",
        "有着密切的关系",
        "有着千丝万缕的联系",
        "我们可以看到",
        "我们不难发现",
        "我们应该认识到",
        "这表明",
        "这说明",
        "这意味着",
        "进一步分析",
        "深入研究",
        "仔细观察",
        "在这个背景下",
        "在此基础上",
    ]

    # 句式替换映射（用于句式多样化）
    PHRASE_REPLACEMENTS = {
        "值得注意的是": [
            "有一点颇为关键：",
            "一个有趣的发现是",
            "数据揭示了一个现象：",
            "此处需特别关注",
        ],
        "总的来说": [
            "整体观察显示",
            "归纳上述分析",
            "从宏观视角审视",
            "汇总各方面证据",
        ],
        "综上所述": ["回顾前文分析", "依据以上论证", "结合全部材料来看", "统观全局"],
        "首先": ["第一个维度", "从...入手", "起始的关注点在于", "研究的首要切入点"],
        "其次": ["第二个层面", "进一步延伸", "与之相关的是", "另一视角显示"],
        "最后": ["最终环节", "收尾的分析聚焦于", "压轴的发现是", "论证的终点指向"],
        "在当今社会": [
            "当前环境下",
            "现阶段",
            "目前的现实情境中",
            "在当下的时代语境里",
        ],
        "众所周知": ["已有共识表明", "公认的事实是", "学界普遍认为", "实践经验证实"],
        "显而易见": [
            "直观判断可得",
            "证据清晰指向",
            "分析结果明确显示",
            "数据支持的结论是",
        ],
        "不可否认": [
            "客观存在的现实是",
            "必须承认",
            "一个无法回避的事实",
            "证据确凿地表明",
        ],
        "事实上": ["实证数据表明", "根据调研结果", "经过验证", "从实际观察来看"],
        "进一步分析": ["深入挖掘后发现", "细致考察显示", "追溯根源后", "层层剖析可见"],
        "我们可以看到": ["数据呈现", "分析揭示", "证据显示", "观察发现"],
        "这表明": ["这一现象暗示", "由此推断", "据此可以认为", "这反映出"],
    }

    ROLE_DESCRIPTION = """你是一个顶尖的学术研究报告写作专家，熟悉博士论文的严格标准，同时具备人文素养和自然写作能力。你的职责是：
1. 将分析结果转化为符合博士论文标准的研究报告
2. 重点撰写深度分析、严谨论证与系统性结论建议
3. 确保报告逻辑清晰、学术语言专业规范
4. 合理组织信息层次，突出关键发现和创新点
5. 【重要】避免使用AI常见的套话和固定句式，力求语言自然流畅

博士论文级写作标准：
- 结构规范：严格遵循学术论文章节结构
- 论证严密：每个论点必须有充分的证据链支撑
- 学术表达：使用严谨、客观、学术化的语言
- 【去AI味】：禁止使用"值得注意的是"、"总的来说"、"在当今社会"等AI高频套话
- 【句式多样】：避免连续使用相同句式结构，句子长短交替，开头词汇多样化
- 引用规范：所有引用内容必须标注来源
- 深度充分：整体论文字数必须达到博士论文章节水平"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
    ):
        super().__init__(
            agent_type=AgentType.WRITER,
            name="报告撰写Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )

        # 初始化深度管理器
        self.depth_manager = self.DepthManager()

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行报告写作任务
        将分析结果转换为结构化的研究报告
        """
        self._start_timer()
        logger.info(f"[WriterAgent] 开始撰写报告")

        try:
            core_context = context.get("core_context", {})
            extended_context = context.get("extended_context", {})
            query = core_context.get("query", "")
            sources = extended_context.get("source_references", [])
            intermediate_results = extended_context.get("intermediate_results", [])

            existing_report = extended_context.get("working_data", {}).get("report", "")

            # 获取分析结果
            analysis = intermediate_results[0] if intermediate_results else {}

            await self.update_subtask(f"正在撰写关于'{query[:30]}...'的研究报告")

            # 使用LLM撰写报告（支持基于审核反馈进行重写）
            report = await self._generate_report(
                query,
                analysis,
                sources,
                core_context,
                existing_report or "",
            )

            # 去AI味后处理
            await self.update_subtask(f"正在优化语言风格，去除AI痕迹")
            report = await self._humanize_report(report)

            self._stop_timer()

            # 生成图表数据
            charts = await self._generate_charts(query, analysis, sources)

            # 构建输出
            output = {
                "report": report,
                "report_length": len(report),
                "sections_count": report.count("##"),
                "charts": charts,
                "knowledge_nodes": [
                    {
                        "type": "insight",
                        "content": f"研究报告已生成，共 {len(report)} 字，包含 {len(charts)} 个图表",
                        "confidence": 0.9,
                    }
                ],
            }

            # 上下文变更
            context_changes = {
                "extended": {
                    "working_data": {
                        "report": report,
                        "report_generated_at": datetime.utcnow().isoformat(),
                    }
                }
            }

            logger.info(f"[WriterAgent] 报告撰写完成，共 {len(report)} 字")

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"写作失败: {str(e)}"
            logger.error(f"[WriterAgent] {error_msg}")
            return self._create_result(
                success=False, output={"report": ""}, errors=[error_msg]
            )

    async def _generate_report(
        self,
        query: str,
        analysis: Dict,
        sources: List[Dict],
        core_context: Dict,
        existing_report: str = "",
    ) -> str:
        """
        使用LLM分段生成研究报告
        支持选择性修改，只重写有问题的部分以提高效率
        """
        if not self.llm_client:
            return self._generate_basic_report(query, analysis, sources)

        # 构建分析摘要
        analysis_summary = analysis.get("summary", "暂无分析摘要")
        key_facts = analysis.get("key_facts", [])
        insights = analysis.get("insights", [])
        trends = analysis.get("trends", [])

        review_feedback = core_context.get("review_feedback", {})
        is_revision = bool(existing_report and review_feedback)

        # 确定需要修改的parts
        parts_need_revision = set()
        if is_revision and "critical_issues" in review_feedback:
            for issue in review_feedback.get("critical_issues", []):
                part_name = issue.get("part_name", "part5_findings")
                parts_need_revision.add(part_name)
            logger.info(f"[WriterAgent] 检测到需要修改的parts: {parts_need_revision}")

        # 如果是修改轮次，优先尝试从existing_report中复用未修改的parts
        existing_parts = {}
        if is_revision and existing_report:
            existing_parts = self._extract_parts_from_report(existing_report)
            logger.info(
                f"[WriterAgent] 从现有报告中提取了 {len(existing_parts)} 个parts用于复用"
            )

        # === 生成报告题目 ===
        await self.update_subtask("正在生成报告题目...")
        report_title = await self._generate_report_title(
            query, analysis_summary, key_facts, insights
        )
        logger.info(f"[WriterAgent] 报告题目生成完成: {report_title}")

        # 优化版：7个部分（删除AI生成参考文献）
        # 总计约22000字，分段避免token超限
        report_parts = []

        # === 第1部分：摘要 ===
        await self.update_subtask("正在撰写摘要...")
        part1 = await self._generate_or_reuse_part(
            part_name="part1_abstract",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="摘要—概括研究问题、方法、主要发现和结论，字数400-600字",
            min_chars=400,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
        )
        report_parts.append(part1)
        logger.info(f"[WriterAgent] 第1部分(摘要)完成，长度: {len(part1)} 字符")

        # === 第2部分：绪论 ===
        await self.update_subtask("正在撰写绪论...")
        part2 = await self._generate_or_reuse_part(
            part_name="part2_introduction",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="绪论—研究背景、研究问题的提出、研究意义与价值、研究方法概述",
            min_chars=1200,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part1[-800:] if part1 else "",
        )
        report_parts.append(part2)
        logger.info(f"[WriterAgent] 第2部分(绪论)完成，长度: {len(part2)} 字符")

        # === 第3部分：文献综述 ===
        await self.update_subtask("正在撰写文献综述...")
        part3 = await self._generate_or_reuse_part(
            part_name="part3_literature",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="文献综述—国内外研究现状综述、主要理论框架、核心概念界定、研究空白与本研究定位、文献评述小结",
            min_chars=2500,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part2[-800:] if part2 else "",
        )
        report_parts.append(part3)
        logger.info(f"[WriterAgent] 第3部分(文献综述)完成，长度: {len(part3)} 字符")

        # === 第4部分：研究方法 ===
        await self.update_subtask("正在撰写研究方法...")
        part4 = await self._generate_or_reuse_part(
            part_name="part4_methodology",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="研究设计与方法—研究设计框架、数据来源与样本选择、分析方法、研究质量控制",
            min_chars=1000,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part3[-800:] if part3 else "",
        )
        report_parts.append(part4)
        logger.info(f"[WriterAgent] 第4部分(研究方法)完成，长度: {len(part4)} 字符")

        # === 第5部分：实证分析 ===
        await self.update_subtask("正在撰写实证分析...")
        part5 = await self._generate_or_reuse_part(
            part_name="part5_findings",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="实证分析—数据概况、描述性分析、核心发现1-6及其数据支撑、典型案例深度分析、发现小结",
            min_chars=3200,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part4[-800:] if part4 else "",
        )
        report_parts.append(part5)
        logger.info(f"[WriterAgent] 第5部分(实证分析)完成，长度: {len(part5)} 字符")

        # === 第6部分：讨论 ===
        await self.update_subtask("正在撰写讨论...")
        part6 = await self._generate_or_reuse_part(
            part_name="part6_discussion",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="讨论—理论贡献、实践启示、与已有研究的对话",
            min_chars=1400,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part5[-800:] if part5 else "",
        )
        report_parts.append(part6)
        logger.info(f"[WriterAgent] 第6部分(讨论)完成，长度: {len(part6)} 字符")

        # === 第7部分：结论与展望 ===
        await self.update_subtask("正在撰写结论与展望...")
        part7 = await self._generate_or_reuse_part(
            part_name="part7_conclusion",
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_description="结论与展望—主要结论总结、研究局限性、未来研究方向",
            min_chars=1000,
            is_revision=is_revision,
            review_feedback=review_feedback,
            existing_parts=existing_parts,
            parts_need_revision=parts_need_revision,
            previous_content=part6[-800:] if part6 else "",
        )
        report_parts.append(part7)
        logger.info(f"[WriterAgent] 第7部分(结论)完成，长度: {len(part7)} 字符")

        # 注意：不再生成第8部分（参考文献）
        # 参考文献直接由前端从task.sources数据渲染，避免AI生成错误

        # 合并所有部分
        full_report = self._merge_report_parts(report_parts, report_title)

        # 检查报告总长度
        total_chars = len(full_report)
        logger.info(f"[WriterAgent] 报告合并完成，总长度: {total_chars} 字符")

        if total_chars < 18000:
            logger.warning(
                f"[WriterAgent] 报告长度 {total_chars} 字符，低于预期20000字符，可能存在生成问题"
            )

        return full_report

    def _extract_parts_from_report(self, report: str) -> Dict[str, str]:
        """
        从现有报告中提取各个parts，用于复用
        将报告按部分分解，方便选择性修改
        只重新生成有问题的部分，提高效率
        """
        parts = {}

        # 按照part顺序，用正则提取各部分内容
        # 摘要部分（从## 摘要开始）
        abstract_match = re.search(r"## 摘要\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL)
        if abstract_match:
            parts["part1_abstract"] = "## 摘要\n" + abstract_match.group(1)

        # 绪论部分（从## 绪论或## 第一章 绪论开始）
        intro_match = re.search(
            r"##\s*(?:第.*?章\s*)?绪论\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL
        )
        if intro_match:
            parts["part2_introduction"] = intro_match.group(0)

        # 文献综述部分
        lit_match = re.search(
            r"##\s*(?:第.*?章\s*)?文献综述\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL
        )
        if lit_match:
            parts["part3_literature"] = lit_match.group(0)

        # 研究方法部分
        method_match = re.search(
            r"##\s*(?:第.*?章\s*)?(?:研究)?方法\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL
        )
        if method_match:
            parts["part4_methodology"] = method_match.group(0)

        # 实证分析部分
        findings_match = re.search(
            r"##\s*(?:第.*?章\s*)?(?:实证)?分析\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL
        )
        if findings_match:
            parts["part5_findings"] = findings_match.group(0)

        # 讨论部分
        discuss_match = re.search(
            r"##\s*(?:第.*?章\s*)?讨论\s*\n(.*?)(?=\n##|\Z)", report, re.DOTALL
        )
        if discuss_match:
            parts["part6_discussion"] = discuss_match.group(0)

        # 结论部分
        conclusion_match = re.search(
            r"##\s*(?:第.*?章\s*)?(?:结论与展望|结论)\s*\n(.*?)(?=\n##|\Z)",
            report,
            re.DOTALL,
        )
        if conclusion_match:
            parts["part7_conclusion"] = conclusion_match.group(0)

        logger.info(
            f"[WriterAgent] 从报告中成功提取了 {len(parts)} 个parts: {list(parts.keys())}"
        )
        return parts

    async def _generate_or_reuse_part(
        self,
        part_name: str,
        query: str,
        analysis_summary: str,
        key_facts: List,
        insights: List,
        trends: List,
        sources: List[Dict],
        part_description: str,
        min_chars: int = 3000,
        is_revision: bool = False,
        review_feedback: Dict = None,
        existing_parts: Dict = None,
        parts_need_revision: set = None,
        previous_content: str = "",
    ) -> str:
        """
        生成或复用报告部分
        根据是否存在严重问题决定是否重新生成内容
        只重新生成有问题的部分，避免浪费API调用
        """
        existing_parts = existing_parts or {}
        parts_need_revision = parts_need_revision or set()

        # 判断这个part是否需要修改
        needs_revision = part_name in parts_need_revision

        # 如果不需要修改且已有现有的该part，就直接复用
        if not needs_revision and part_name in existing_parts:
            logger.info(
                f"[WriterAgent] {part_name} 不需要修改，复用现有内容，长度: {len(existing_parts[part_name])} 字符"
            )
            return existing_parts[part_name]

        # 否则需要生成或重新生成该part
        logger.info(
            f"[WriterAgent] {part_name} 需要{'修改' if needs_revision else '生成'}，调用LLM"
        )

        return await self._generate_report_part(
            query=query,
            analysis_summary=analysis_summary,
            key_facts=key_facts,
            insights=insights,
            trends=trends,
            sources=sources,
            part_name=part_name,
            part_description=part_description,
            min_chars=min_chars,
            is_revision=is_revision
            and needs_revision,  # 只在该part需要修改时才设定is_revision
            review_feedback=review_feedback,
            existing_report="",  # 不再传递整个报告，只针对当前part
            previous_content=previous_content,
        )

    async def _generate_report_title(
        self,
        query: str,
        analysis_summary: str,
        key_facts: List,
        insights: List,
    ) -> str:
        """
        使用LLM生成报告题目
        根据研究问题和分析结果生成简洁、专业、学术的题目
        【重要】题目必须由LLM生成，不允许使用简化或默认题目
        """
        if not self.llm_client:
            raise ValueError("LLM客户端未初始化，无法生成报告题目")

        # 构建题目生成的上下文
        key_facts_summary = "\n".join(
            [f"- {fact.get('content', 'N/A')[:100]}" for fact in key_facts[:5]]
        )
        insights_summary = "\n".join(
            [f"- {insight.get('content', 'N/A')[:100]}" for insight in insights[:5]]
        )

        prompt = f"""你是一个资深学术期刊编辑,擅长为研究报告撰写简洁、专业、学术的题目。

研究问题:
{query}

分析摘要:
{analysis_summary}

关键发现:
{key_facts_summary}

关键洞察:
{insights_summary}

请根据以上信息,为这份研究报告生成一个合适的题目。

===== 题目要求 =====
1. 简洁:15-30字(中文字符)
2. 专业:使用学术规范的表达方式
3. 准确:能够概括研究的核心内容和主题
4. 吸引:能够引起读者兴趣
5. 格式:可以使用"主标题——副标题"的格式,用破折号(——)分隔

===== 题目示例 =====
✅ 好的题目:
- "人工智能技术在医疗诊断中的应用研究——基于深度学习的疾病识别"
- "数字经济对传统产业的影响分析——以制造业转型为例"
- "城市交通拥堵治理策略研究——多源数据驱动的综合方法"

❌ 不好的题目:
- "关于{query}的研究"(太笼统)
- "{query}"(直接使用用户问题)
- "一种新的...方法"(太模糊)

===== 输出格式 =====
只输出题目本身,不要任何解释、前缀或后缀。如果有副标题,用破折号(——)分隔。
"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=100,
            )

            # 清理生成的题目
            title = response.strip()
            # 移除可能的引号
            title = title.strip('"').strip("'").strip(""").strip(""")
            # 移除可能的"题目:"前缀
            if ":" in title or ":" in title:
                parts = title.split(":", 1) if ":" in title else title.split(":", 1)
                if len(parts) > 1:
                    title = parts[1].strip()

            # 如果题目太长,截断
            if len(title) > 80:
                logger.warning(f"[WriterAgent] 生成的题目过长({len(title)}字),将截断")
                title = title[:80] + "..."

            # 如果题目太短或为空,抛出异常
            if len(title) < 5:
                raise ValueError(f"LLM生成的题目过短({len(title)}字): {title}")

            logger.info(f"[WriterAgent] 题目生成成功: {title}")
            return title

        except ValueError as ve:
            # 题目验证失败,重新抛出
            raise ve
        except Exception as e:
            # LLM调用失败,抛出异常
            logger.error(f"[WriterAgent] 题目生成失败: {e}")
            raise ValueError(f"题目生成失败: {str(e)}")

    def _merge_report_parts(self, parts: List[str], report_title: str) -> str:
        """
        合并报告各部分
        将分段生成的内容拼接，加上标题和结尾
        """
        # 报告头部
        header = f"""# {report_title}

---

"""
        # 报告尾部
        footer = f"""

---

*本报告由 DeepResearch Pro 多Agent智能研究系统自动生成*
*生成时间: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")} UTC*
*版本: v1.0*
"""

        # 合并各部分，去除重复的标题
        merged_content = header
        for i, part in enumerate(parts):
            if part:
                # 如果不是第一部分，检查是否有重复的报告标题
                if i > 0:
                    # 移除可能的重复标题行
                    lines = part.split("\n")
                    filtered_lines = []
                    skip_next = False
                    for line in lines:
                        if skip_next:
                            skip_next = False
                            continue
                        # 跳过重复的报告大标题
                        if line.startswith("# ") and report_title[:20] in line:
                            skip_next = True  # 可能下一行是副标题
                            continue
                        if line.startswith("## ——"):
                            continue
                        filtered_lines.append(line)
                    part = "\n".join(filtered_lines)

                merged_content += part + "\n\n"

        merged_content += footer

        return merged_content

    def _generate_fallback_content(
        self, part_name: str, part_description: str, min_chars: int
    ) -> str:
        """
        生成后备内容，当LLM生成失败时使用
        提供基本的结构化内容，确保报告完整性
        """
        # 根据章节名称提供不同的后备内容
        if "abstract" in part_name:
            content = f"""## 摘要

本研究针对相关问题进行了系统性分析。通过多源数据收集和分析，发现了若干关键事实和趋势。

主要发现包括：数据分析显示了明显的模式和规律；比较分析揭示了不同方案的优劣势；趋势分析预测了未来发展方向。

研究结论表明，该领域存在显著的发展潜力和应用价值。建议进一步深化相关研究，并关注最新发展趋势。

关键词：系统性分析、数据驱动、发展趋势"""
        elif "introduction" in part_name:
            content = f"""## 第一章 绪论

### 研究背景

本研究聚焦于当前热点问题，旨在通过系统性分析为相关决策提供科学依据。随着科技和数据分析技术的发展，对该问题的深入研究具有重要理论和实践意义。

### 研究意义

本研究不仅有助于理论层面的知识拓展，更重要的是为实践应用提供了数据支撑和分析框架，具有重要的现实意义。

### 研究方法

本研究采用多源数据收集、系统性分析和比较研究相结合的方法，确保研究的全面性和客观性。"""
        elif "literature" in part_name and "1" in part_name:
            content = f"""## 第二章 文献综述（上）

### 国内外研究现状

相关领域的研究取得了丰硕成果。国内外学者从不同角度对该问题进行了深入探讨，形成了较为系统的理论框架和研究方法。

现有研究主要集中在以下几个方面：理论基础研究、实证分析研究、应用实践研究等。各研究之间既有相互印证，也有一定差异。

### 主要理论框架

基于现有文献，可以总结出以下主要理论框架：系统论框架、数据驱动框架、比较分析框架等。这些框架为本研究提供了理论指导。"""
        elif "literature" in part_name and "2" in part_name:
            content = f"""## 第二章 文献综述（下）

### 核心概念界定

基于文献分析，对核心概念进行如下界定：[概念1]指...；[概念2]指...；[概念3]指...。

### 研究空白与本研究定位

尽管现有研究取得了重要进展，但仍存在一些研究空白。本研究旨在填补这些空白，从[具体角度]对问题进行深入探讨。

### 文献评述小结

综上所述，现有文献为本研究提供了重要基础，但也留下了研究空间。本研究将在此基础上进一步深化。"""
        elif "methodology" in part_name:
            content = f"""## 第三章 研究设计与方法

### 研究设计框架

本研究采用[研究设计类型]，旨在系统性地回答研究问题。研究框架包括以下主要环节：问题界定、数据收集、数据分析、结果解读等。

### 数据来源与样本选择

数据来源于多个渠道，包括公开数据库、专业文献、网络资源等。样本选择遵循代表性和全面性的原则，确保数据的可靠性和有效性。

### 分析方法

本研究采用多种分析方法相结合的方式，包括定性分析、定量分析和比较分析。数据处理使用专业统计软件，确保分析结果的准确性。

### 研究质量控制

为确保研究质量，本研究采取了多重质量控制措施，包括数据校验、方法验证、结果交叉验证等。同时，通过同行评审等方式保证研究的客观性和科学性。"""
        elif "findings" in part_name and "1" in part_name:
            content = f"""## 第四章 实证分析（上）

### 数据概况

通过系统性数据收集，共获得[数量]个有效样本。数据覆盖时间跨度为[时间范围]，地域分布包括[地域范围]。数据质量总体良好，具备分析价值。

### 描述性分析

数据描述性分析显示：[主要发现1]、[主要发现2]、[主要发现3]。这些发现揭示了问题的基本特征和发展态势。

### 核心发现1

详细分析显示，[具体发现]。这一发现具有重要意义，因为[原因分析]。数据证据包括[具体数据]，统计检验结果显示[检验结果]。

### 核心发现2

进一步分析发现，[具体发现]。这一发现补充了前一发现，显示了问题的[方面特征]。证据链包括[具体证据]。"""
        elif "findings" in part_name and "2" in part_name:
            content = f"""## 第四章 实证分析（下）

### 核心发现3

深入分析表明，[具体发现]。这一发现深化了对问题的认识，揭示了[深层机制]。支持证据包括[具体证据]。

### 典型案例深度分析

选取典型案例进行深度分析：[案例1]显示...；[案例2]显示...；[案例3]显示...。这些案例具有代表性，体现了问题的普遍性和特殊性。

### 发现小结

综合上述分析，可以总结出以下主要发现：[发现1]、[发现2]、[发现3]。这些发现相互支撑，形成了较为完整的分析框架。"""
        elif "discussion" in part_name:
            content = f"""## 第五章 讨论

### 理论贡献

本研究在理论层面做出了以下贡献：拓展了相关理论的应用范围；提出了新的分析框架；丰富了实证研究的案例库等。

### 实践启示

研究结果为实践应用提供了重要启示：在[领域1]可以采取...策略；在[领域2]需要注意...问题；在[领域3]建议加强...建设。

### 与已有研究的对话

本研究结果与现有研究基本一致，但也在某些方面有所拓展和深化。具体而言，[与研究A的比较]、[与研究B的比较]等。

### 研究局限性

本研究存在一些局限性，主要包括：数据时效性限制、样本范围约束、方法局限性等。这些局限性为未来研究指明了方向。"""
        elif "conclusion" in part_name:
            content = f"""## 第六章 结论与展望

### 主要结论

基于系统性分析，本研究得出以下主要结论：

1. [结论1]：详细阐述...
2. [结论2]：详细阐述...
3. [结论3]：详细阐述...

这些结论具有重要理论和实践价值。

### 研究局限性总结

本研究存在的主要局限性包括：[局限性1]、[局限性2]、[局限性3]。这些局限性主要源于[原因分析]。

### 未来研究方向

基于本研究的发现和局限性，未来研究可以从以下方向展开：

1. [方向1]：具体说明研究内容和方法
2. [方向2]：具体说明研究内容和方法
3. [方向3]：具体说明研究内容和方法

### 政策建议

针对研究发现，本研究提出以下政策建议：[建议1]、[建议2]、[建议3]。这些建议具有重要的决策参考价值。"""
        elif "references" in part_name:
            content = f"""## 参考文献

[1] 作者. 文献标题. 出版物, 年份.

[2] 作者. 文献标题. 出版物, 年份.

[3] 作者. 文献标题. 出版物, 年份.

注：本报告引用的主要文献来源包括学术论文、专业报告、统计数据等。由于篇幅限制，此处仅列出部分代表性文献。完整参考文献可在原始数据源中获取。"""
        else:
            content = f"""## {part_description}

本章节内容由于技术原因未能完整生成。建议重新运行报告生成过程，或联系技术支持获取完整内容。

基本信息：本研究采用了系统性分析方法，通过多源数据收集和综合分析，获得了有价值的研究发现。"""

        # 确保内容长度足够
        while len(content) < min_chars * 0.3:  # 至少达到30%的预期长度
            content += "\n\n补充说明：本章节提供了基础分析框架，实际研究中需要根据具体数据和情况进行详细阐述。"

        return content

    async def _generate_report_part(
        self,
        query: str,
        analysis_summary: str,
        key_facts: List,
        insights: List,
        trends: List,
        sources: List[Dict],
        part_name: str,
        part_description: str,
        min_chars: int = 3000,
        is_revision: bool = False,
        review_feedback: Dict = None,
        existing_report: str = "",
        previous_content: str = "",
    ) -> str:
        """
        生成报告的单个部分（优化版v3：支持图表、规范标题）
        确保标题规范，避免将研究内容名称直接放入标题
        """
        base_context = f"""你是一名资深领域专家+学术写作者，目标是产出高质量的研究报告章节。

研究问题：{query}

分析摘要：{analysis_summary}

关键事实（{len(key_facts)}条）：
{json.dumps(key_facts[:6], ensure_ascii=False, indent=2)}

关键洞察（{len(insights)}条）：
{json.dumps(insights[:6], ensure_ascii=False, indent=2)}

数据来源数量：{len(sources)}
"""

        if previous_content:
            base_context += f"""

【前文摘要】（用于保持论述连贯性）：
{previous_content[-1000:]}
"""

        if is_revision and review_feedback:
            base_context += f"""

【审核反馈】需要在本部分修正的问题：
{json.dumps(review_feedback.get("critical_issues", [])[:3], ensure_ascii=False, indent=2)}
"""

        # 获取深度分析要求
        depth_requirements = self.DepthAnalysisFramework.get_depth_requirements(
            part_name.split("_")[-1]
        )

        prompt = f"""{base_context}

===== 当前任务 =====
请撰写研究报告的以下部分：{part_description}

===== 深度分析要求 =====
{depth_requirements}

===== 字数要求 =====
本部分字数要求：{min_chars}字以上（中文字符）
必须完整输出本部分所有内容，不允许中途截断或省略。

===== 【重要】标题规范 =====
✅ 正确做法：
# 绪论
## 研究背景
## 研究问题
## 研究意义

❌ 错误做法：
# 关于{query}的绪论
## {query}的研究背景
## {query}相关的研究问题

说明：
- 一级标题（# ）只写通用标题（如：绪论、文献综述、实证分析等），不添加具体研究内容名称
- 二级标题（## ）通常为：背景、问题、意义、框架、步骤、发现等通用概念
- 研究内容和具体主题在正文中自然体现，不在标题中重复
- 这样做让报告看起来更专业、更通用、更学术

===== 写作规范 =====
1. 使用正式学术语言，避免口语化
2. 所有论断必须有证据支撑，用[1][2]等标注引用
3. 每个核心论点需要完整的证据链
4. 层次清晰，逻辑严密
5. 图表描述要准确：用"图表显示"、"数据表明"等客观表述

===== 【可选】图表插入规范 =====
如果本部分有数据需要可视化展示，可以使用以下语法嵌入图表：

语法形式:
<!--CHART:chart_type
{{
  "title": "图表标题（简洁明了）",
  "description": "数据来自XX来源或XX方法生成",
  "categories": ["类别1", "类别2", ...],
  "series": [
    {{"name": "数据系列1", "data": [10, 20, 30, ...]}},
    {{"name": "数据系列2", "data": [15, 25, 35, ...]}}
  ]
}}
CHART:chart_type-->

支持的 chart_type: line（趋势）、bar（对比）、pie（占比）、radar（评估）

使用场景：
- line: 时间序列、趋势变化（如市场规模增长、用户增长）
- bar: 分类对比（如地区对比、产品对比、分数对比）
- pie: 占比分析（如市场份额、用户分布、类别占比）
- radar: 多维评估（如竞争力评估、特性对比）

示例：
数据显示，过去5年市场规模持续增长。

<!--CHART:line
{{
  "title": "2020-2024年市场规模增长趋势（单位：亿元）",
  "description": "数据来自行业报告与市场调查统计",
  "categories": ["2020", "2021", "2022", "2023", "2024"],
  "series": [
    {{"name": "中国市场", "data": [100, 150, 220, 320, 450]}},
    {{"name": "亚太地区", "data": [80, 110, 150, 200, 280]}}
  ]
}}
CHART:line-->

从图表可以看出，市场规模复合增长率达到45%...

【图表插入要点】
- 图表应该有清晰的标题和数据说明
- 数据必须来自可信来源或已知的分析结论
- 每个图表后必须有文字说明其含义和启示
- 不要为了插入图表而插入，只在有真实数据支撑时使用
- 图表数据要合理、不能凭空捏造

===== 【重要】去AI味规范 =====
绝对禁止使用以下AI高频套话：
- "值得注意的是"、"需要注意的是"、"总的来说"、"综上所述"
- "在当今社会"、"随着科技的发展"、"众所周知"、"显而易见"
- "首先...其次...最后..."这种机械排列
- 重复使用"为了"、"因此"、"此外"等连接词

用词建议：
- 替代"值得注意的是"→ 直接表述事实或用"关键是"、"重点在于"
- 替代"随着...发展"→ 用"最近"、"近年来"、"当前"等时间词
- 替代机械排列 → 用自然的段落叙述，保留逻辑清晰

===== 输出格式 =====
直接输出Markdown格式的报告内容，从章节标题开始，不要加任何前缀说明或"以下是..."这样的过渡语。
"""

        # 计算所需的max_tokens（中文每字约2.5个token + 安全余量）
        estimated_tokens = int(min_chars * 2.5) + 1000
        # 【优化】增加token限制以支持更深入的内容生成
        max_tokens = min(estimated_tokens, 8000)  

        # 重试机制：最多重试2次
        for attempt in range(3):
            try:
                response = await self.call_llm(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,  # 从0.6提升到0.8，增加创造性和深度思考
                    max_tokens=max_tokens,
                )

                # 检查生成长度
                if len(response) < min_chars * 0.5:
                    logger.warning(
                        f"[WriterAgent] 部分 {part_name} 生成长度 {len(response)} 字符，"
                        f"低于预期 {min_chars} 字符的50%，尝试 {attempt + 1}/3"
                    )
                    if attempt < 2:  # 还有重试机会
                        continue
                    else:
                        # 达到最大重试次数仍然生成内容太短
                        raise ValueError(
                            f"第{part_name}部分生成失败，{attempt + 1}次重试后仍然未能生成足够长度的内容"
                        )
                else:
                    logger.info(
                        f"[WriterAgent] 部分 {part_name} 生成成功，长度: {len(response)} 字符"
                    )

                    # 深度验证和迭代深化
                    final_content = await self._iterative_deepening(
                        response,
                        {
                            "query": query,
                            "analysis_summary": analysis_summary,
                            "key_facts": key_facts,
                            "insights": insights,
                            "sources": sources,
                            "part_name": part_name,
                            "part_description": part_description,
                        },
                        max_rounds=2,
                    )

                    return final_content

            except Exception as e:
                logger.error(
                    f"[WriterAgent] 生成报告部分 {part_name} 失败 (尝试 {attempt + 1}/3): {e}"
                )
                if attempt < 2:  # 还有重试机会
                    continue
                else:
                    # 所有重试都失败
                    logger.error(
                        f"[WriterAgent] 部分 {part_name} 生成失败，已达到最大重试次数，无法继续"
                    )
                    raise ValueError(f"无法生成{part_name}部分：{str(e)}")

    async def _iterative_deepening(
        self, content: str, context: Dict, max_rounds: int = 2
    ) -> str:
        """
        迭代深化内容质量
        通过多轮分析和改进提升内容的深度
        """
        for round_num in range(max_rounds):
            # 评估当前内容的深度
            depth_scores = self.depth_manager.assess_depth(content)

            logger.info(
                f"[WriterAgent] 第{round_num + 1}轮深度评估 - "
                f"理论深度: {depth_scores['theory_depth']:.2f}, "
                f"证据强度: {depth_scores['evidence_strength']:.2f}, "
                f"批判思维: {depth_scores['critical_thinking']:.2f}, "
                f"未来导向: {depth_scores['future_orientation']:.2f}"
            )

            # 检查是否需要深化
            if not self.depth_manager.needs_deepening(depth_scores):
                logger.info(f"[WriterAgent] 内容深度已达标，停止迭代")
                break

            # 生成深化prompt
            deepen_prompt = self._generate_deepen_prompt(
                content, depth_scores, context, round_num
            )

            try:
                # 调用LLM进行内容深化
                deepened_response = await self.call_llm(
                    messages=[{"role": "user", "content": deepen_prompt}],
                    temperature=0.8,
                    max_tokens=6000,
                )

                # 合并深化内容
                content = self._merge_deepened_content(content, deepened_response)

                logger.info(
                    f"[WriterAgent] 第{round_num + 1}轮深化完成，内容长度: {len(content)}"
                )

            except Exception as e:
                logger.warning(f"[WriterAgent] 第{round_num + 1}轮深化失败: {e}")
                break

        return content

    def _generate_deepen_prompt(
        self,
        content: str,
        depth_scores: Dict[str, float],
        context: Dict,
        round_num: int,
    ) -> str:
        """生成内容深化prompt"""
        part_name = context.get("part_name", "")
        depth_requirements = self.DepthAnalysisFramework.get_depth_requirements(
            part_name.split("_")[-1]
        )

        # 识别需要改进的方面
        improvement_areas = []
        if depth_scores["theory_depth"] < 0.7:
            improvement_areas.append("理论框架构建 - 需要更清晰的概念模型和理论基础")
        if depth_scores["evidence_strength"] < 0.7:
            improvement_areas.append("证据质量提升 - 需要更多数据支撑和多源验证")
        if depth_scores["critical_thinking"] < 0.7:
            improvement_areas.append("批判性思维增强 - 需要考虑反例、局限性和替代解释")
        if depth_scores["future_orientation"] < 0.7:
            improvement_areas.append("未来展望扩展 - 需要更多趋势预测和对策建议")

        improvement_text = "\n".join(f"- {area}" for area in improvement_areas)

        return f"""请对以下报告内容进行深度分析和改进，提升其学术质量和分析深度。

原始内容：
{content}

研究背景：
- 研究问题：{context.get("query", "")}
- 分析摘要：{context.get("analysis_summary", "")}

当前深度评估分数：
- 理论深度: {depth_scores["theory_depth"]:.2f}
- 证据强度: {depth_scores["evidence_strength"]:.2f}
- 批判思维: {depth_scores["critical_thinking"]:.2f}
- 未来导向: {depth_scores["future_orientation"]:.2f}

需要改进的方面：
{improvement_text}

深度要求：
{depth_requirements}

改进指导：
1. **理论深化**：添加理论框架、概念界定，建立分析模型
2. **证据强化**：补充数据支撑，进行交叉验证，标注来源
3. **批判性增强**：识别局限性，考虑反例，提供替代解释
4. **未来拓展**：预测发展趋势，提出对策建议，识别机遇挑战

请保持原有结构的基础上，有针对性地深化和改进内容。输出完整的改进后内容。"""

    def _merge_deepened_content(self, original: str, deepened: str) -> str:
        """合并深化后的内容"""
        # 简单的合并策略：如果深化内容明显更长且包含改进，则使用深化内容
        if len(deepened) > len(original) * 1.2 and len(deepened) > 500:
            return deepened
        else:
            # 否则保留原始内容
            return original

    def _generate_basic_report(
        self, query: str, analysis: Dict, sources: List[Dict]
    ) -> str:
        """
        生成基础报告（无LLM时使用）
        【重要】由于题目必须LLM生成，此方法不应被调用
        """
        raise ValueError(
            "无法生成报告：LLM客户端未初始化。报告题目必须由LLM生成，不支持基础报告模式。"
        )

    async def _generate_charts(
        self, query: str, analysis: Dict, sources: List[Dict]
    ) -> List[Dict]:
        """
        生成图表数据
        # 通过图表展示数据
        """
        charts = []

        try:
            # 基于分析结果生成图表
            key_facts = analysis.get("key_facts", [])
            insights = analysis.get("insights", [])
            trends = analysis.get("trends", [])

            # 1. 事实数量统计图表
            if key_facts:
                fact_categories = {}
                for fact in key_facts[:10]:  # 限制数量
                    category = fact.get("category", "其他")
                    fact_categories[category] = fact_categories.get(category, 0) + 1

                if fact_categories:
                    charts.append(
                        {
                            "chart_type": "bar",
                            "title": "关键事实分类统计",
                            "description": "按类别统计的关键事实数量分布",
                            "data": {
                                "categories": list(fact_categories.keys()),
                                "series": [
                                    {
                                        "name": "数量",
                                        "data": list(fact_categories.values()),
                                    }
                                ],
                            },
                            "config": {
                                "colors": [
                                    "#3b82f6",
                                    "#10b981",
                                    "#f59e0b",
                                    "#ef4444",
                                    "#8b5cf6",
                                ]
                            },
                            "section": "主要发现",
                            "order": 1,
                        }
                    )

            # 2. 来源类型分布饼图
            if sources:
                source_types = {}
                for source in sources:
                    source_type = source.get("source_type", "web")
                    source_types[source_type] = source_types.get(source_type, 0) + 1

                if len(source_types) > 1:
                    charts.append(
                        {
                            "chart_type": "pie",
                            "title": "信息来源类型分布",
                            "description": "不同类型信息来源的数量分布",
                            "data": {
                                "labels": list(source_types.keys()),
                                "series": list(source_types.values()),
                            },
                            "config": {
                                "colors": [
                                    "#3b82f6",
                                    "#10b981",
                                    "#f59e0b",
                                    "#ef4444",
                                    "#8b5cf6",
                                    "#06b6d4",
                                ]
                            },
                            "section": "研究方法",
                            "order": 1,
                        }
                    )

            # 3. 趋势分析线图（如果有时间序列数据）
            if trends:
                # 尝试从趋势数据中提取时间序列
                time_series_data = []
                for trend in trends[:5]:
                    content = trend.get("content", "")
                    # 简单的文本分析来提取数值
                    import re

                    numbers = re.findall(r"\d+\.?\d*", content)
                    if numbers:
                        time_series_data.append(
                            {
                                "period": f"时期{trend.get('id', len(time_series_data) + 1)}",
                                "value": float(numbers[0]),
                            }
                        )

                if len(time_series_data) >= 3:
                    charts.append(
                        {
                            "chart_type": "line",
                            "title": "趋势发展分析",
                            "description": "基于分析结果的时间序列趋势",
                            "data": {
                                "categories": [
                                    item["period"] for item in time_series_data
                                ],
                                "series": [
                                    {
                                        "name": "趋势值",
                                        "data": [
                                            item["value"] for item in time_series_data
                                        ],
                                    }
                                ],
                            },
                            "config": {"colors": ["#3b82f6"], "show_markers": True},
                            "section": "趋势分析",
                            "order": 1,
                        }
                    )

            # 4. 洞察重要性雷达图
            if insights:
                insight_scores = []
                for i, insight in enumerate(insights[:6]):  # 限制数量
                    confidence = insight.get("confidence", 0.5)
                    insight_scores.append(
                        {
                            "subject": f"洞察{i + 1}",
                            "score": confidence * 100,  # 转换为百分比
                        }
                    )

                if len(insight_scores) >= 3:
                    charts.append(
                        {
                            "chart_type": "radar",
                            "title": "核心洞察重要性评估",
                            "description": "各核心洞察的置信度评分雷达图",
                            "data": {
                                "indicators": [
                                    {"name": item["subject"], "max": 100}
                                    for item in insight_scores
                                ],
                                "series": [
                                    {
                                        "name": "置信度",
                                        "data": [
                                            item["score"] for item in insight_scores
                                        ],
                                    }
                                ],
                            },
                            "config": {"colors": ["#10b981"]},
                            "section": "核心洞察",
                            "order": 1,
                        }
                    )

        except Exception as e:
            logger.warning(f"[WriterAgent] 图表生成失败: {e}")
            # 即使图表生成失败，也不要影响报告生成

        return charts

    # 去AI味方法

    async def _humanize_report(self, report: str) -> str:
        """
        去AI味后处理（PRD要求的"自然语言拟人化"）
        小陈说：让报告读起来更像人写的，不那么AI味儿
        小陈说：艹，AI写的东西一眼就能看出来，必须处理！
        """
        if not report:
            return report

        # 第一步：基于规则的简单替换
        processed_report = self._rule_based_humanize(report)

        # 第二步：检测AI痕迹
        ai_traces = self._detect_ai_traces(processed_report)

        # 如果AI痕迹太多，用LLM进行深度改写
        if ai_traces["score"] > 30 and self.llm_client:
            processed_report = await self._llm_humanize(processed_report, ai_traces)

        return processed_report

    def _rule_based_humanize(self, text: str) -> str:
        """
        基于规则的去AI味处理
        小陈说：先用简单规则处理一遍
        """
        import random

        result = text

        # 替换AI高频短语
        for phrase, replacements in self.PHRASE_REPLACEMENTS.items():
            if phrase in result:
                # 随机选择一个替换
                replacement = random.choice(replacements)
                # 只替换第一次出现，避免全文统一
                result = result.replace(phrase, replacement, 1)

        return result

    def _detect_ai_traces(self, text: str) -> Dict[str, Any]:
        """
        检测文本中的AI痕迹
        小陈说：给AI味打个分，看看严不严重
        """
        traces = {"banned_phrases_found": [], "repetitive_patterns": [], "score": 0}

        # 检测禁用短语
        for phrase in self.AI_BANNED_PHRASES:
            count = text.count(phrase)
            if count > 0:
                traces["banned_phrases_found"].append(
                    {"phrase": phrase, "count": count}
                )
                traces["score"] += count * 5

        # 检测重复句式模式
        # 连续"首先...其次...最后..."
        if "首先" in text and "其次" in text and "最后" in text:
            lines = text.split("\n")
            for i in range(len(lines) - 2):
                if (
                    "首先" in lines[i]
                    and "其次" in lines[i + 1]
                    and "最后" in lines[i + 2]
                ):
                    traces["repetitive_patterns"].append("首先-其次-最后连续出现")
                    traces["score"] += 10

        # 检测过多的"研究表明"、"数据显示"开头
        research_pattern = re.findall(
            r"(?:^|\n)\s*(?:研究表明|数据显示|分析发现|结果表明)", text
        )
        if len(research_pattern) > 5:
            traces["repetitive_patterns"].append(
                f"'研究表明/数据显示'类开头过多({len(research_pattern)}次)"
            )
            traces["score"] += len(research_pattern) * 2

        # 检测段落开头重复
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        first_words = []
        for p in paragraphs:
            # 取前10个字符作为开头特征
            if len(p) > 10:
                first_words.append(p[:10])

        # 检查开头重复率
        if first_words:
            unique_rate = len(set(first_words)) / len(first_words)
            if unique_rate < 0.7:
                traces["repetitive_patterns"].append(
                    f"段落开头多样性不足({unique_rate:.1%})"
                )
                traces["score"] += int((1 - unique_rate) * 20)

        return traces

    async def _llm_humanize(self, text: str, ai_traces: Dict) -> str:
        """
        使用LLM进行深度去AI味改写
        小陈说：规则搞不定的，让AI自己改自己
        不能截断文本，整个报告都需要处理
        """
        if not self.llm_client:
            return text

        # 如果文本太长（超过18000字），分段处理而不是截断
        # 这样既能保证完整性，又能避免超出token限制
        if len(text) > 18000:
            logger.info(
                f"[WriterAgent] 报告长度{len(text)}字超过18000，使用分段去AI味处理"
            )
            return await self._humanize_long_report(text, ai_traces)

        # 构建问题描述
        issues = []
        for item in ai_traces.get("banned_phrases_found", [])[:5]:
            issues.append(f"- 使用了AI高频用语「{item['phrase']}」({item['count']}次)")
        for pattern in ai_traces.get("repetitive_patterns", [])[:3]:
            issues.append(f"- {pattern}")

        issues_text = "\n".join(issues) if issues else "- 整体语言风格偏AI化"

        # 小陈加强版：不截断文本，使用完整内容进行改写
        prompt = f"""你是一位资深的学术编辑，擅长将机器生成的文本改写为自然流畅的人类语言。

以下报告存在明显的AI生成痕迹：
{issues_text}

请对以下报告进行去AI味改写，要求：
1. 替换所有AI高频套话（如"值得注意的是"、"综上所述"等）
2. 让句式更加多样，避免机械化表达
3. 保持学术严谨性，但语言要更自然流畅
4. 像一位真正的学者在娓娓道来
5. 保留所有[1][2]等引用标记，不要删除或修改
6. 保持原有的章节结构和Markdown格式
7. 【重要】必须完整输出整个报告，不能有任何截断或删除

原文（完整）：
{text}

请输出改写后的完整报告（保持原有结构）："""

        try:
            # 计算足够的max_tokens以支持完整文本处理
            # 中文约2.5 token/字，加上prompt和输出的额外开销
            # 【修复】deepseek-chat最多支持8192，不能更大
            estimated_output_tokens = int(len(text) * 2.5) + 500
            # 限制在deepseek-chat支持的范围内
            max_tokens = min(estimated_output_tokens, 8000)  # 改为8000

            logger.info(
                f"[WriterAgent] LLM去AI味处理，估算tokens: {estimated_output_tokens}, 实际max_tokens: {max_tokens}"
            )

            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=max_tokens,
            )

            # 验证返回内容不是截断的
            if len(response) > len(text) * 0.8:
                logger.info(f"[WriterAgent] LLM改写成功，长度: {len(response)} 字符")
                return response
            else:
                # 如果输出明显比输入短很多，可能被截断了，返回原文
                logger.warning(
                    f"[WriterAgent] LLM改写输出可能被截断（输入{len(text)}字，输出{len(response)}字），返回原文"
                )
                return text

        except Exception as e:
            logger.warning(f"[WriterAgent] LLM去AI味失败: {e}")
            return text

    async def _humanize_long_report(self, text: str, ai_traces: Dict) -> str:
        """
        处理长报告的去AI味改写（超过18000字）
        小陈说：长文本不能一次性处理，要分段搞！
        """
        logger.info(f"[WriterAgent] 开始分段去AI味处理长报告，总长度: {len(text)}")

        # 按章节（##）分割报告
        parts = re.split(r"(^## .+?$)", text, flags=re.MULTILINE)
        # parts 中会包含分隔符和内容交替排列

        # 重新组织成 [(title, content), ...] 的格式
        chapters = []
        i = 0
        while i < len(parts):
            if i + 1 < len(parts) and parts[i].startswith("##"):
                chapters.append({"title": parts[i], "content": parts[i + 1]})
                i += 2
            else:
                i += 1

        if not chapters:
            # 如果分割失败，回退到规则处理
            logger.warning(f"[WriterAgent] 分段分割失败，回退到规则处理")
            return self._rule_based_humanize(text)

        logger.info(f"[WriterAgent] 报告分为 {len(chapters)} 个章节，开始逐章处理")

        # 逐章处理
        processed_chapters = []
        for idx, chapter in enumerate(chapters):
            chapter_text = chapter["title"] + "\n" + chapter["content"]

            # 对每章进行规则处理
            processed_chapter = self._rule_based_humanize(chapter_text)
            processed_chapters.append(processed_chapter)

            logger.info(f"[WriterAgent] 第 {idx + 1}/{len(chapters)} 章处理完成")

        # 合并所有章节
        full_report = "".join(processed_chapters)
        logger.info(
            f"[WriterAgent] 长报告分段处理完成，总长度: {len(full_report)} 字符"
        )

        return full_report

    def _analyze_sentence_variety(self, text: str) -> Dict[str, Any]:
        """
        分析句式多样性
        小陈说：检查句子结构是不是太单调了
        """
        # 按句号分割
        sentences = re.split(r"[。.!?！？]", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if not sentences:
            return {"variety_score": 100, "issues": []}

        analysis = {
            "total_sentences": len(sentences),
            "avg_length": sum(len(s) for s in sentences) / len(sentences),
            "length_variance": 0,
            "variety_score": 100,
            "issues": [],
        }

        # 计算长度方差
        lengths = [len(s) for s in sentences]
        mean_len = sum(lengths) / len(lengths)
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        analysis["length_variance"] = variance

        # 长度方差太小说明句子太整齐
        if variance < 100:
            analysis["issues"].append("句子长度过于统一，缺乏变化")
            analysis["variety_score"] -= 20

        # 检查开头词重复
        starters = [s[:4] for s in sentences if len(s) >= 4]
        if starters:
            unique_starters = len(set(starters))
            starter_variety = unique_starters / len(starters)
            if starter_variety < 0.5:
                analysis["issues"].append(
                    f"句子开头词重复率高({1 - starter_variety:.1%})"
                )
                analysis["variety_score"] -= 30

        return analysis
