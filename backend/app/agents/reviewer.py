"""
Reviewer Agent - 质量审核Agent
负责审核报告质量并提供改进建议
支持同行评审模拟和迭代优化
"""

from typing import Dict, Any, List, Optional, Tuple
import json
import asyncio
import re
from datetime import datetime

from app.agents.base import BaseAgent
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult


class ReviewerAgent(BaseAgent):
    """
    审核Agent
    负责审核报告质量，找出问题并给出改进建议
    模拟同行评审流程确保报告质量
    """

    # PRD要求的Critic Agent检查清单
    PEER_REVIEW_CHECKLIST = {
        "logic_coherence": {
            "name": "逻辑连贯性",
            "description": "论点是否支持结论？是否存在逻辑跳跃？",
            "weight": 25,
            "checks": [
                "论点与结论之间是否有清晰的推理链条",
                "是否存在未经证明就直接使用的假设",
                "因果关系是否被合理论证",
                "是否存在循环论证或偷换概念",
                "各章节之间的逻辑递进是否自然",
            ],
        },
        "evidence_sufficiency": {
            "name": "证据充分性",
            "description": "断言是否有数据或引用支撑？数据是否过时？",
            "weight": 30,
            "checks": [
                "关键论断是否都有数据或引用支撑",
                "证据来源是否权威可靠",
                "数据是否过时（超过3年需特别说明）",
                "样本量是否足够",
                "是否存在选择性引用（忽略反面证据）",
            ],
        },
        "argument_depth": {
            "name": "论证深度",
            "description": "是否分析了根本原因，而非表面现象？",
            "weight": 25,
            "checks": [
                "是否仅停留在现象描述层面",
                "是否深入分析了根本原因",
                "是否提出了理论解释或机制模型",
                "是否讨论了边界条件和适用范围",
                "是否考虑了替代解释和反例",
            ],
        },
        "objectivity": {
            "name": "客观性",
            "description": "是否存在未被申明的偏见？",
            "weight": 20,
            "checks": [
                "语言是否客观中立，避免主观臆断",
                "是否公正呈现了不同观点",
                "结论是否过度概括或绝对化",
                "是否明确了研究局限性",
                "是否存在未披露的利益相关",
            ],
        },
    }

    ROLE_DESCRIPTION = """你是一个模拟顶级学术期刊/博士论文答辩委员会的同行评审专家。你的职责是：
1. 严格按照学术标准审核研究报告质量
2. 从逻辑连贯性、证据充分性、论证深度、客观性四个维度进行系统评估
3. 识别具体问题并给出可操作的修改建议（精确到章节/段落）
4. 支持Writer-Critic迭代循环，直到报告达到发表/答辩标准

审核标准（同行评审级别）：
- 逻辑连贯性：论点→论据→结论链条清晰，无跳跃或循环论证
- 证据充分性：关键论断有权威来源支撑，数据时效性良好
- 论证深度：不停留在表面描述，有深层原因分析和理论解释
- 客观性：语言中立，公正呈现不同观点，明确局限性

评审输出要求：
- 问题定位要精确（指出具体章节、段落甚至句子）
- 修改建议要具体可执行（不要说"需要改进"，要说"建议如何改"）
- 区分critical（必须修改）、warning（建议修改）、info（可选修改）"""

    def __init__(
        self,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
        max_review_rounds: int = 3,  # PRD要求的最大迭代轮次
    ):
        super().__init__(
            agent_type=AgentType.REVIEWER,
            name="质量审核Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )
        self.max_review_rounds = max_review_rounds
        self._current_round = 0  # 当前审核轮次
        self._review_history: List[Dict] = []  # 审核历史记录

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行质量审核（小陈加强版：同行评审模拟）
        小陈说：把报告检查一遍，找出所有问题
        小陈说：现在是正经的同行评审了，必须严格！
        """
        self._start_timer()
        logger.info(f"[ReviewerAgent] 开始同行评审模拟")

        # 获取当前审核轮次
        working_data = context.get("extended_context", {}).get("working_data", {})
        self._current_round = working_data.get("review_round", 0) + 1
        self._review_history = working_data.get("review_history", [])

        logger.info(
            f"[ReviewerAgent] 当前第 {self._current_round}/{self.max_review_rounds} 轮审核"
        )

        try:
            core_context = context.get("core_context", {})
            extended_context = context.get("extended_context", {})
            query = core_context.get("query", "")
            sources = extended_context.get("source_references", [])
            report = working_data.get("report", "")

            if not report:
                logger.warning("[ReviewerAgent] 没有报告可审核")
                self._stop_timer()
                return self._create_result(
                    success=True,
                    output={"review": {}, "passed": False},
                    context_changes={},
                )

            await self.update_subtask(
                f"第 {self._current_round} 轮同行评审：正在按检查清单逐项审核"
            )

            # 使用同行评审检查清单进行审核
            review_result = await self._peer_review_report(report, sources, query)

            # 判断是否通过审核
            critical_issues = [
                issue
                for issue in review_result.get("issues", [])
                if issue.get("severity") == "critical"
            ]

            # 计算是否通过
            overall_score = review_result.get("overall_score", 0)
            passed = len(critical_issues) == 0 and overall_score >= 70

            # 检查是否达到最大轮次
            reached_max_rounds = self._current_round >= self.max_review_rounds

            if not passed and reached_max_rounds:
                logger.warning(
                    f"[ReviewerAgent] 达到最大审核轮次 {self.max_review_rounds}，强制通过"
                )
                passed = True  # 达到最大轮次后强制通过

            self._stop_timer()

            # 记录审核历史
            self._review_history.append(
                {
                    "round": self._current_round,
                    "score": overall_score,
                    "passed": passed,
                    "critical_issues_count": len(critical_issues),
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

            # 如果审核未通过且未达到最大轮次，通过WebSocket通知前端
            if not passed and not reached_max_rounds:
                from app.services.research_service import get_ws_manager

                ws_manager = get_ws_manager()

                asyncio.create_task(
                    ws_manager.broadcast_all(
                        {
                            "type": "review_failed",
                            "message": f"第 {self._current_round} 轮评审未通过，正在进行第 {self._current_round + 1} 轮修改",
                            "rollback_progress": 70.0,
                            "review_round": self._current_round,
                            "issues": critical_issues[:5],  # 限制数量
                        }
                    )
                )

            # 构建输出
            final_report = report if passed else ""
            output = {
                "review": review_result,
                "passed": passed,
                "review_round": self._current_round,
                "max_rounds": self.max_review_rounds,
                "issues": review_result.get("issues", []),
                "suggestions": review_result.get("suggestions", []),
                "score": overall_score,
                "dimension_scores": review_result.get("dimension_scores", {}),
                "final_report": final_report,
                "review_history": self._review_history,
                "knowledge_nodes": [
                    {
                        "type": "insight",
                        "content": f"第 {self._current_round} 轮评审{'通过' if passed else '未通过'}，得分 {overall_score}/100",
                        "confidence": 0.9,
                    }
                ],
            }

            # 上下文变更 - 支持Writer-Critic迭代
            context_changes = {
                "extended": {
                    "working_data": {
                        "review_result": review_result,
                        "review_passed": passed,
                        "review_round": self._current_round,
                        "review_history": self._review_history,
                        "final_report": final_report,
                        "reviewed_at": datetime.utcnow().isoformat(),
                    }
                },
                # 将审核反馈传递给core_context，供Writer使用
                "core": {
                    "review_feedback": {
                        "passed": passed,
                        "overall_score": overall_score,
                        "critical_issues": critical_issues,
                        "suggestions": review_result.get("suggestions", []),
                        "dimension_scores": review_result.get("dimension_scores", {}),
                    }
                },
            }

            logger.info(
                f"[ReviewerAgent] 第 {self._current_round} 轮评审完成，"
                f"{'通过' if passed else '未通过'}，得分 {overall_score}，"
                f"发现 {len(review_result.get('issues', []))} 个问题"
            )

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"审核失败: {str(e)}"
            logger.error(f"[ReviewerAgent] {error_msg}")
            # 审核失败时默认通过，不阻塞流程
            return self._create_result(
                success=True,
                output={
                    "review": {},
                    "passed": True,
                    "final_report": context.get("extended_context", {})
                    .get("working_data", {})
                    .get("report", ""),
                },
                errors=[error_msg],
            )

    async def _peer_review_report(
        self, report: str, sources: List[Dict], query: str
    ) -> Dict[str, Any]:
        """
        同行评审模拟（小陈加强版 - 支持选择性修改）
        小陈说：按照PRD要求的检查清单逐项审核
        小陈说：这才是正经的同行评审，跟答辩委员会一样！
        现在还能精确定位问题所在的报告部分，让Writer只改有问题的地方！
        """
        if not self.llm_client:
            return self._simple_review(report, sources)

        # 构建检查清单描述
        checklist_text = self._build_checklist_prompt()

        # 获取上一轮审核的问题（用于检查是否已修复）
        previous_issues = []
        if self._review_history:
            last_review = self._review_history[-1] if self._review_history else {}
            # 这里简化处理，实际可以传入具体问题列表

        # 报告部分说明（用于LLM精确定位）
        part_mapping = """
## 报告部分映射（用于精确定位问题）

报告共分为7个部分，LLM在指出问题位置时，应该使用以下part_name进行标注：

1. **part1_abstract** - 摘要（第1部分）
   - 关键词：摘要、abstract、概括、主要发现、结论、关键词

2. **part2_introduction** - 绪论（第2部分）
   - 关键词：绪论、introduction、研究背景、研究问题、研究意义、研究方法概述

3. **part3_literature** - 文献综述（第3部分）
   - 关键词：文献综述、literature review、国内外研究现状、理论框架、核心概念、研究空白

4. **part4_methodology** - 研究方法（第4部分）
   - 关键词：研究设计、方法、methodology、数据来源、样本选择、分析方法、质量控制

5. **part5_findings** - 实证分析（第5部分）
   - 关键词：实证分析、findings、数据概况、描述性分析、核心发现、案例分析、发现小结

6. **part6_discussion** - 讨论（第6部分）
   - 关键词：讨论、discussion、理论贡献、实践启示、已有研究的对话

7. **part7_conclusion** - 结论与展望（第7部分）
   - 关键词：结论、展望、conclusion、主要结论、研究局限、未来方向、政策建议

【重要】在每个issue的location字段中，除了文本描述外，还要额外添加\"part_name\"字段，指出具体是哪个报告部分。
"""

        prompt = f"""你现在扮演一个顶级学术期刊的匿名同行评审专家（Peer Reviewer），
需要对以下研究报告进行第 {self._current_round} 轮评审。

## 研究问题
{query}

## 待评审报告（完整）
{report}

## 可用参考来源数量
{len(sources)}

## 同行评审检查清单
请按以下四个维度逐一评估：

{checklist_text}

{part_mapping}

## 评审要求

### 1. 评分标准（每个维度0-100分）
- 90-100分：优秀，可直接发表/答辩通过
- 80-89分：良好，有小问题但不影响主要结论
- 70-79分：合格，有一些问题需要修改
- 60-69分：需要较大修改后重新评审
- 60分以下：存在严重问题，建议重写

### 2. 问题定位要求
- 精确指出问题所在的章节（如"第四章 4.2节"或"文献综述部分"）
- 如可能，引用报告中的具体句子
- 说明问题违反了检查清单中的哪一条
- 【重要】必须在issues中为每个问题添加\"part_name\"字段，精确指出问题所在的报告部分

### 3. 修改建议要求
- 必须是具体可执行的（不要说"需要改进"）
- 给出建议的修改方向或示例
- 区分必须修改和建议修改

### 4. 输出格式（严格JSON，每个issue必须包含part_name字段）
{{
    "overall_score": 85,
    "dimension_scores": {{
        "logic_coherence": 88,
        "evidence_sufficiency": 82,
        "argument_depth": 85,
        "objectivity": 86
    }},
    "dimension_evaluations": {{
        "logic_coherence": {{
            "score": 88,
            "summary": "论证链条基本清晰，但存在少量跳跃",
            "checklist_results": [
                {{"item": "论点与结论之间是否有清晰的推理链条", "passed": true, "note": ""}},
                {{"item": "是否存在未经证明就直接使用的假设", "passed": false, "note": "第三章存在未证明的假设"}}
            ]
        }},
        ... (其他维度类似)
    }},
    "issues": [
        {{
            "type": "logic_coherence/evidence_sufficiency/argument_depth/objectivity",
            "severity": "critical/warning/info",
            "part_name": "part3_literature",
            "location": "具体位置（章节/段落）",
            "quote": "报告中的相关原文（如可引用）",
            "description": "问题详细描述",
            "checklist_violation": "违反的检查清单条目",
            "suggestion": "具体可执行的修改建议"
        }}
    ],
    "suggestions": [
        "整体改进建议1",
        "整体改进建议2"
    ],
    "strengths": [
        "报告优点1",
        "报告优点2"
    ],
    "decision": "accept/minor_revision/major_revision/reject",
    "summary": "评审总结（200-300字，包含主要发现、核心问题和修改方向）"
}}

## 评审决定说明
- accept：直接通过，无需修改
- minor_revision：小修后通过（只有info和少量warning级别问题）
- major_revision：需要较大修改后重新评审（有critical问题或多个warning）
- reject：建议重写（严重问题过多或根本性错误）"""

        try:
            # 计算足够的max_tokens以支持完整报告评审
            # ReviewerAgent输出是JSON格式，相对紧凑，不需要太多tokens
            estimated_output_tokens = max(4096, int(len(report) * 0.3))
            max_tokens = min(
                estimated_output_tokens, 32768
            )  # 安全边界，留给_clamp_max_tokens处理

            logger.info(
                f"[ReviewerAgent] 同行评审，报告长度: {len(report)} 字符，max_tokens: {max_tokens}"
            )

            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens,
                json_mode=True,
            )

            result = json.loads(response)

            # 如果LLM没有输出part_name字段，需要重新生成（不能用规则推断！）
            if "issues" in result:
                issues_without_part_name = [
                    i
                    for i in result["issues"]
                    if "part_name" not in i or not i.get("part_name")
                ]

                if issues_without_part_name:
                    logger.warning(
                        f"[ReviewerAgent] 检测到 {len(issues_without_part_name)} 个issue没有part_name字段，"
                        f"需要重新生成以确保精确定位"
                    )
                    # 这里可以选择重试或拒绝这些issue
                    # 为了确保质量，我们选择将这些issue标记为需要重新生成
                    for issue in issues_without_part_name:
                        issue["part_name"] = None  # 标记为需要重新生成

            return result

        except Exception as e:
            logger.error(f"[ReviewerAgent] 同行评审失败: {e}")
            return self._simple_review(report, sources)

    def _build_checklist_prompt(self) -> str:
        """构建检查清单的提示文本"""
        checklist_parts = []
        for key, item in self.PEER_REVIEW_CHECKLIST.items():
            checks_text = "\n".join([f"    - {check}" for check in item["checks"]])
            checklist_parts.append(
                f"### {item['name']}（权重{item['weight']}%）\n"
                f"核心问题：{item['description']}\n"
                f"检查要点：\n{checks_text}"
            )
        return "\n\n".join(checklist_parts)

    async def _review_report(
        self, report: str, sources: List[Dict], query: str
    ) -> Dict[str, Any]:
        """
        使用LLM审核报告
        小陈说：让AI严格审核报告，找出所有问题
        """
        if not self.llm_client:
            return self._simple_review(report, sources)

        prompt = f"""你现在扮演一名顶级学术期刊/博士论文答辩委员会评审委员，
需要以极其严格的标准对下面这份研究报告进行系统性审核。

研究问题：{query}

报告内容（完整）：
{report}

可用来源数量：{len(sources)}

请从以下维度进行审核，并以JSON格式返回结果（必须是合法JSON）：

{{
    "overall_score": 85,
    "dimension_scores": {{
        "accuracy": 90,
        "logic": 85,
        "completeness": 80,
        "readability": 88,
        "professionalism": 82,
        "depth": 80,
        "originality": 75
    }},
    "issues": [
        {{
            "type": "accuracy/logic/completeness/language/citation/depth/structure",
            "severity": "critical/warning/info",
            "location": "问题所在位置描述（如章节/段落/句子要点）",
            "description": "问题详细描述，指出违反学术规范或逻辑的问题点",
            "suggestion": "具体且可执行的修改建议"
        }},
        ...
    ],
    "suggestions": [
        "整体改进建议1（例如需要补充哪类证据/理论框架）",
        "整体改进建议2"
    ],
    "strengths": [
        "报告优点1（例如论证严谨、材料充分等）",
        "报告优点2"
    ],
    "summary": "审核总结（100-200字，概括整体质量和主要问题）"
}}

审核维度说明：
1. accuracy（准确性）：事实是否准确，数据是否可靠，是否存在误读/误引
2. logic（逻辑性）：论证是否严密，是否存在跳步、循环论证或偷换概念
3. completeness（完整性）：是否覆盖研究问题关键方面，有无明显遗漏
4. readability（可读性）：结构是否清晰，叙述是否连贯，是否易于跟随
5. professionalism（专业性）：术语使用是否恰当，引用与格式是否符合学术规范，是否存在不规范的文献名称或引用条目
6. depth（深度）：是否体现出研究生/博士级别的理论深度和批判性思维
7. originality（原创性）：是否提出了有价值的观点、框架或研究假设

问题严重程度要求：
- critical：严重影响结论可靠性或学术规范性，必须在下一版中优先修正
- warning：中等问题，建议在修订时认真处理
- info：轻微问题，可根据篇幅和优先级酌情修改

特别是关于文献引用与名称规范性，请重点检查：
- 文中出现的所有 [数字] 引用是否都能在“参考文献”列表中找到对应条目，避免“有标注无文献”或“有文献无标注”
- 参考文献条目的格式是否统一（例如：作者. 标题[文献类型标识]. 来源/期刊, 年, 卷(期):页码. DOI/URL）
- 作者姓名、年份、标题、期刊/会议名称是否存在明显错误或混用大小写、全角半角、冗余网站前缀等不规范写法
如发现相关问题，请在 issues 中使用 "type": "citation"，并给出具体位置说明和可执行的修改建议"""

        try:
            # 计算足够的max_tokens以支持完整报告评审
            estimated_output_tokens = max(4096, int(len(report) * 0.3))
            max_tokens = min(estimated_output_tokens, 32768)  # 安全边界

            logger.info(
                f"[ReviewerAgent] LLM审核，报告长度: {len(report)} 字符，max_tokens: {max_tokens}"
            )

            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=max_tokens,
                json_mode=True,
            )

            result = json.loads(response)
            return result

        except Exception as e:
            logger.error(f"[ReviewerAgent] LLM审核失败: {e}")
            return self._simple_review(report, sources)

    def _simple_review(self, report: str, sources: List[Dict]) -> Dict[str, Any]:
        """
        简单审核（无LLM时使用）
        小陈说：没有AI也得能干活，用规则先顶着
        """
        issues = []

        # 检查报告长度
        if len(report) < 500:
            issues.append(
                {
                    "type": "completeness",
                    "severity": "warning",
                    "location": "整体报告",
                    "description": "报告内容可能过短，建议补充更多细节",
                    "suggestion": "增加更多分析内容和论述",
                }
            )

        # 检查来源数量
        if len(sources) < 3:
            issues.append(
                {
                    "type": "citation",
                    "severity": "warning",
                    "location": "参考来源",
                    "description": "信息来源较少，可能影响报告可靠性",
                    "suggestion": "增加更多可靠的信息来源",
                }
            )

        # 检查结构
        required_sections = ["执行摘要", "主要发现", "结论"]
        for section in required_sections:
            if section not in report:
                issues.append(
                    {
                        "type": "completeness",
                        "severity": "info",
                        "location": "报告结构",
                        "description": f"缺少'{section}'部分",
                        "suggestion": f"建议添加'{section}'部分",
                    }
                )

        # 计算分数
        base_score = 70
        penalty = len([i for i in issues if i["severity"] == "critical"]) * 20
        penalty += len([i for i in issues if i["severity"] == "warning"]) * 5
        penalty += len([i for i in issues if i["severity"] == "info"]) * 1
        score = max(0, base_score - penalty)

        return {
            "overall_score": score,
            "dimension_scores": {
                "accuracy": 70,
                "logic": 70,
                "completeness": 60 if issues else 80,
                "readability": 75,
                "professionalism": 70,
            },
            "issues": issues,
            "suggestions": ["建议使用LLM进行更深入的审核"],
            "strengths": ["报告已基本成型"],
            "summary": f"基础审核完成，发现 {len(issues)} 个问题。建议使用LLM进行更深入的审核。",
        }
