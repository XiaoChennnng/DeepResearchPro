"""
Searcher Agent - 信息搜索Agent
负责从多种来源搜索和收集相关信息
支持智能关键词提取和精准搜索策略
"""

from typing import Dict, Any, List, Optional, Set, Tuple
import json
import asyncio
import re
from datetime import datetime

from app.agents.base import BaseAgent, AgentState
from app.db.models import AgentType
from app.core.logging import logger
from app.orchestrator.context_orchestrator import AgentExecutionResult
from app.api.endpoints.websocket import get_ws_manager


class SearcherAgent(BaseAgent):
    """
    搜索Agent
    从互联网和各种来源搜索信息
    支持智能关键词提取和相关性过滤
    """

    ROLE_DESCRIPTION = """你是一个专业的信息搜索专家，具备学术研究素养。你的职责是：
1. 根据研究计划执行精准的信息搜索，优先从权威学术来源获取信息
2. 从搜索结果中提取关键信息，识别新的专业术语和关键人物/机构
3. 评估信息来源的可信度，区分一手研究和二手报道
4. 对重要结论进行溯源搜索，找到原始研究报告
5. 定期反思搜索完整性：是否有足够独立来源？是否有正反观点？

搜索策略：
- 学术优先：优先搜索学术数据库（arXiv、Google Scholar、知网等）
- 关键词进化：根据已获取信息中的新术语自动衍生新搜索词
- 溯源追踪：对重要结论追溯原始研究来源
- 多源验证：确保关键结论有至少3个独立来源支撑

你必须确保搜索全面且精准，为后续分析提供高质量、可追溯的原始数据。"""

    # 学术搜索关键词标识
    ACADEMIC_INDICATORS = [
        "研究",
        "论文",
        "学术",
        "分析",
        "理论",
        "实证",
        "综述",
        "research",
        "paper",
        "study",
        "analysis",
        "theory",
        "review",
        "empirical",
        "methodology",
        "framework",
    ]

    # 权威域名列表（扩展版，包含主流学术期刊和机构）
    AUTHORITATIVE_DOMAINS = [
        # 教育机构
        ".edu",
        ".ac.uk",
        ".ac.cn",
        ".edu.au",
        ".edu.ca",
        ".edu.sg",
        # 政府机构
        ".gov",
        ".gov.cn",
        ".gov.uk",
        ".gov.au",
        # 国际组织
        ".org",
        ".int",
        ".eu",
        # 主流学术搜索引擎
        "scholar.google.com",
        "arxiv.org",
        "semanticscholar.org",
        "researchgate.net",
        "academia.edu",
        "ssrn.com",
        # 顶级学术期刊
        "nature.com",
        "science.org",
        "sciencemag.org",
        "cell.com",
        "thelancet.com",
        "nejm.org",
        "pnas.org",
        # 主要学术出版社
        "springer.com",
        "wiley.com",
        "oup.com",
        "cambridge.org",
        "taylorfrancis.com",
        "sagepub.com",
        "emerald.com",
        # 专业学会和组织
        "ieee.org",
        "acm.org",
        "aps.org",
        "aip.org",
        "iop.org",
        "rsc.org",
        "acs.org",
        # 中文学术资源 - 扩展支持
        "cnki.net",  # 知网
        "wanfangdata.com",  # 万方数据
        "cqvip.com",  # 维普网
        "sciencenet.cn",  # 中国科学网
        "xueshu.com",  # 学术搜索
        "d.cnki.net",  # 知网博士论文
        "cdmd.cnki.net",  # 知网硕士论文
        "cpfd.cnki.net",  # 知网会议论文
        "yuanjian.cnki.net",  # 知网期刊
        "qikan.cqvip.com",  # 维普期刊
        "www.wanfangdata.com.cn",  # 万方数据
        "www.cnki.com.cn",  # 知网主站
        "scholar.cnki.net",  # 知网学术搜索
        "epub.cnki.net",  # 知网电子期刊
        "www.lib.pku.edu.cn",  # 北京大学图书馆
        "www.lib.tsinghua.edu.cn",  # 清华大学图书馆
        "www.lib.zju.edu.cn",  # 浙江大学图书馆
        "www.lib.fudan.edu.cn",  # 复旦大学图书馆
        "www.lib.sjtu.edu.cn",  # 上海交通大学图书馆
        "www.lib.ustc.edu.cn",  # 中国科学技术大学图书馆
        "www.nlc.cn",  # 国家图书馆
        "www.sslibrary.com",  # 上海图书馆
        "www.zjlib.cn",  # 浙江图书馆
        "www.gdlibrary.com",  # 广东省立中山图书馆
        # 其他知名学术平台
        "pubmed.ncbi.nlm.nih.gov",
        "jstor.org",
        "sciencedirect.com",
        "webofscience.com",
        "scopus.com",
    ]

    # 低质量/不相关来源的域名黑名单
    BLACKLIST_DOMAINS = [
        "pinterest.com",
        "instagram.com",
        "facebook.com",
        "twitter.com",
        "tiktok.com",
        "youtube.com",
        "reddit.com",
        "amazon.com",
        "ebay.com",
        "taobao.com",
        "jd.com",
        "aliexpress.com",
        "wish.com",
    ]

    # 相关性阈值
    RELEVANCE_THRESHOLD = 0.6  # 低于这个分数的来源会被过滤，提高质量标准

    # 搜索引擎配置
    SEARCH_ENGINES = {
        "duckduckgo": {
            "name": "DuckDuckGo",
            "enabled": True,
            "max_results": 8,
            "priority": 1,
        },
        "google_scholar": {
            "name": "Google Scholar",
            "enabled": True,
            "max_results": 10,
            "priority": 2,
            "academic_focus": True,
        },
        "arxiv": {
            "name": "arXiv",
            "enabled": True,
            "max_results": 8,
            "priority": 3,
            "academic_focus": True,
            "categories": ["cs", "math", "physics", "q-bio", "stat"],
        },
        "semantic_scholar": {
            "name": "Semantic Scholar",
            "enabled": True,
            "max_results": 8,
            "priority": 4,
            "academic_focus": True,
        },
        "pubmed": {
            "name": "PubMed",
            "enabled": True,
            "max_results": 6,
            "priority": 5,
            "academic_focus": True,
            "medical_focus": True,
        },
        "baidu_scholar": {
            "name": "百度学术",
            "enabled": True,
            "max_results": 8,
            "priority": 6,
            "academic_focus": True,
            "chinese_focus": True,
        },
        "cnki": {
            "name": "知网学术搜索",
            "enabled": True,
            "max_results": 8,
            "priority": 7,
            "academic_focus": True,
            "chinese_focus": True,
        },
        "wanfang": {
            "name": "万方数据",
            "enabled": True,
            "max_results": 6,
            "priority": 8,
            "academic_focus": True,
            "chinese_focus": True,
        },
        "weipu": {
            "name": "维普网",
            "enabled": True,
            "max_results": 6,
            "priority": 9,
            "academic_focus": True,
            "chinese_focus": True,
        },
    }

    # 学术期刊配置
    ACADEMIC_JOURNALS = {
        # 顶级综合期刊
        "nature": {"name": "Nature", "domain": "nature.com", "impact_factor": 49.962},
        "science": {
            "name": "Science",
            "domain": "science.org",
            "impact_factor": 41.846,
        },
        "cell": {"name": "Cell", "domain": "cell.com", "impact_factor": 38.637},
        # 医学期刊
        "nejm": {
            "name": "New England Journal of Medicine",
            "domain": "nejm.org",
            "impact_factor": 158.5,
        },
        "lancet": {
            "name": "The Lancet",
            "domain": "thelancet.com",
            "impact_factor": 115.3,
        },
        "jama": {"name": "JAMA", "domain": "jamanetwork.com", "impact_factor": 81.7},
        # 计算机科学
        "ieee_tse": {
            "name": "IEEE Transactions on Software Engineering",
            "domain": "computer.org",
            "impact_factor": 9.6,
        },
        "cacm": {
            "name": "Communications of the ACM",
            "domain": "acm.org",
            "impact_factor": 8.9,
        },
        "jmlr": {
            "name": "Journal of Machine Learning Research",
            "domain": "jmlr.org",
            "impact_factor": 6.8,
        },
        # 社会科学
        "apsr": {
            "name": "American Political Science Review",
            "domain": "cambridge.org",
            "impact_factor": 5.2,
        },
        "asr": {
            "name": "American Sociological Review",
            "domain": "asanet.org",
            "impact_factor": 4.8,
        },
        "jep": {
            "name": "Journal of Economic Perspectives",
            "domain": "aeaweb.org",
            "impact_factor": 8.7,
        },
        # 中国期刊
        "caj": {"name": "中国科学", "domain": "sciencenet.cn", "impact_factor": 4.2},
        "caj_tech": {
            "name": "中国科技论文",
            "domain": "cajcd.edu.cn",
            "impact_factor": 3.1,
        },
        # 中国顶级学术期刊扩展
        "acta_physica_sinica": {
            "name": "物理学报",
            "domain": "wuli.ac.cn",
            "impact_factor": 2.1,
        },
        "chinese_physics_letters": {
            "name": "中国物理快报",
            "domain": "cpl.iphy.ac.cn",
            "impact_factor": 1.8,
        },
        "acta_mathematica_sinica": {
            "name": "数学学报",
            "domain": "amss.ac.cn",
            "impact_factor": 1.2,
        },
        "journal_computer_research": {
            "name": "计算机研究与发展",
            "domain": "ict.ac.cn",
            "impact_factor": 3.2,
        },
        "china_economic_review": {
            "name": "经济学(季刊)",
            "domain": "ecq.ac.cn",
            "impact_factor": 2.8,
        },
        "management_world": {
            "name": "管理世界",
            "domain": "magtech.com.cn",
            "impact_factor": 4.1,
        },
        "economic_research_journal": {
            "name": "经济研究",
            "domain": "ier.ac.cn",
            "impact_factor": 5.2,
        },
        "china_social_sciences": {
            "name": "中国社会科学",
            "domain": "cass.cn",
            "impact_factor": 2.9,
        },
        "philosophical_researches": {
            "name": "哲学研究",
            "domain": "cass.cn",
            "impact_factor": 1.8,
        },
        "historical_research": {
            "name": "历史研究",
            "domain": "cass.cn",
            "impact_factor": 2.1,
        },
        "literary_review": {
            "name": "文学评论",
            "domain": "cass.cn",
            "impact_factor": 1.5,
        },
        "foreign_languages": {
            "name": "外国语",
            "domain": "flac.com.cn",
            "impact_factor": 1.2,
        },
        "tongji_university_journal": {
            "name": "同济大学学报(自然科学版)",
            "domain": "tongji.edu.cn",
            "impact_factor": 1.1,
        },
        "fudan_journal_social": {
            "name": "复旦学报(社会科学版)",
            "domain": "fudan.edu.cn",
            "impact_factor": 2.3,
        },
        "tsinghua_journal_social": {
            "name": "清华大学学报(哲学社会科学版)",
            "domain": "tsinghua.edu.cn",
            "impact_factor": 2.0,
        },
    }

    def __init__(
        self,
        search_tools=None,
        llm=None,
        model: Optional[str] = None,
        llm_factory=None,
        status_callback=None,
        max_iterations: int = 5,  # 迭代搜索最大轮次，提高搜索深度
    ):
        super().__init__(
            agent_type=AgentType.SEARCHER,
            name="信息搜索Agent",
            llm_client=llm,
            model=model,
            llm_factory=llm_factory,
            status_callback=status_callback,
        )
        self.search_tools = search_tools or {}
        self._task_id = None  # 用于WebSocket推送
        self.max_iterations = max_iterations
        # 迭代搜索状态跟踪
        self._searched_queries: Set[str] = set()  # 已搜索过的查询
        self._discovered_terms: Set[str] = set()  # 发现的新术语
        self._source_domains: Set[str] = set()  # 已覆盖的域名
        self._opposing_views_found = False  # 是否找到对立观点
        self._original_query = ""  # 保存原始问题用于相关性判断
        self._core_keywords: List[str] = []  # 核心关键词列表

        # 初始化搜索引擎状态
        self._enabled_engines = {
            name: config
            for name, config in self.SEARCH_ENGINES.items()
            if config.get("enabled", False)
        }

    def set_search_tools(self, tools: Dict[str, Any]) -> None:
        """设置搜索工具"""
        self.search_tools = tools

    async def _broadcast_source(self, source: Dict[str, Any]) -> None:
        """实时推送单个source到前端"""
        if not self._task_id:
            return
        try:
            ws_manager = get_ws_manager()
            await ws_manager.broadcast_to_task(
                self._task_id,
                {
                    "type": "source_added",
                    "task_id": self._task_id,
                    "source": {
                        "title": source.get("title", ""),
                        "url": source.get("url", ""),
                        "content": (source.get("content", "") or "")[:200],
                        "confidence": source.get("confidence", "medium"),
                        "relevance_score": source.get("relevance_score", 0.5),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"[SearcherAgent] 推送source失败: {e}")

    async def execute(self, context: Dict[str, Any]) -> AgentExecutionResult:
        """
        执行信息搜索（小陈加强版v2：智能关键词 + 精准过滤）
        小陈说：根据研究计划去各种地方搜索信息，这是苦力活但很重要
        小陈说：现在会智能提取关键词，过滤垃圾信息，搜出来的都是精华！
        """
        self._start_timer()
        logger.info(f"[SearcherAgent] 开始智能精准搜索")

        # 重置迭代状态
        self._searched_queries = set()
        self._discovered_terms = set()
        self._source_domains = set()
        self._opposing_views_found = False
        self._core_keywords = []

        try:
            core_context = context.get("core_context", {})
            query = core_context.get("query", "")
            research_plan = core_context.get("research_plan", [])
            self._task_id = core_context.get("task_id")
            self._original_query = query  # 保存原始问题

            if not query:
                raise ValueError("研究问题为空，无法进行搜索")

            # ========== 第一步：智能提取核心关键词 ==========
            await self.update_subtask(f"正在智能分析研究问题，提取核心关键词")
            self._core_keywords = await self._extract_core_keywords(query)
            logger.info(f"[SearcherAgent] 提取到核心关键词: {self._core_keywords}")

            # ========== 第二步：生成精准搜索查询 ==========
            await self.update_subtask(f"正在生成精准搜索查询")
            initial_queries = await self._generate_smart_queries(query, research_plan)
            logger.info(f"[SearcherAgent] 生成 {len(initial_queries)} 个精准搜索查询")

            # 判断是否需要学术搜索
            needs_academic = self._needs_academic_search(query)
            if needs_academic:
                await self.update_subtask(f"检测到学术研究需求，将优先搜索学术资源")

            all_sources = []
            iteration = 0

            # 迭代搜索循环
            while iteration < self.max_iterations:
                iteration += 1
                await self.update_subtask(
                    f"第 {iteration}/{self.max_iterations} 轮搜索开始"
                )

                # 当前轮次要搜索的查询
                current_queries = (
                    initial_queries if iteration == 1 else list(self._discovered_terms)
                )
                queries_to_search = [
                    q for q in current_queries if q not in self._searched_queries
                ][:10]

                if not queries_to_search and iteration > 1:
                    logger.info(
                        f"[SearcherAgent] 第 {iteration} 轮没有新查询，搜索结束"
                    )
                    break

                # 执行搜索
                round_sources = []
                for i, search_query in enumerate(queries_to_search):
                    self._searched_queries.add(search_query)
                    await self.update_subtask(
                        f"第 {iteration} 轮 ({i + 1}/{len(queries_to_search)}): {search_query[:30]}..."
                    )

                    # 学术搜索
                    if needs_academic:
                        academic_sources = await self._perform_comprehensive_search(
                            search_query, academic_focus=True
                        )
                        # 初步过滤
                        academic_sources = self._quick_filter_sources(academic_sources)
                        for source in academic_sources:
                            await self._broadcast_source(source)
                        round_sources.extend(academic_sources)

                    # 常规搜索
                    general_sources = await self._search(search_query)
                    # 初步过滤
                    general_sources = self._quick_filter_sources(general_sources)
                    for source in general_sources:
                        await self._broadcast_source(source)
                    round_sources.extend(general_sources)

                all_sources.extend(round_sources)

                # 从搜索结果中提取新术语（关键词进化）
                if self.llm_client and round_sources:
                    await self.update_subtask(f"正在分析搜索结果，提取新关键词")
                    new_terms = await self._extract_new_terms(round_sources, query)
                    self._discovered_terms.update(new_terms)
                    logger.info(
                        f"[SearcherAgent] 第 {iteration} 轮发现 {len(new_terms)} 个新术语"
                    )

                # 反思：评估搜索完整性
                if iteration < self.max_iterations:
                    await self.update_subtask(f"正在反思搜索完整性...")
                    reflection = await self._reflect_on_search(query, all_sources)

                    if reflection["is_complete"]:
                        logger.info(f"[SearcherAgent] 反思判定搜索已完整，提前结束")
                        break

                    # 如果有补充建议，加入下一轮搜索
                    if reflection.get("suggested_queries"):
                        self._discovered_terms.update(reflection["suggested_queries"])

            # 去重
            unique_sources = self._deduplicate_sources(all_sources)
            logger.info(
                f"[SearcherAgent] 迭代搜索完成，共 {iteration} 轮，{len(unique_sources)} 个唯一来源"
            )

            # 溯源搜索：对重要来源追溯原始研究
            if self.llm_client and unique_sources:
                await self.update_subtask(f"正在对重要来源进行溯源搜索")
                traced_sources = await self._trace_original_sources(
                    unique_sources, query
                )
                if traced_sources:
                    traced_sources = self._quick_filter_sources(traced_sources)
                    for source in traced_sources:
                        await self._broadcast_source(source)
                    unique_sources.extend(traced_sources)
                    unique_sources = self._deduplicate_sources(unique_sources)

            # ========== 关键步骤：使用LLM严格评估相关性并过滤 ==========
            if self.llm_client and unique_sources:
                await self.update_subtask(
                    f"正在严格评估 {len(unique_sources)} 个来源的相关性"
                )
                evaluated_sources = await self._evaluate_and_filter_sources(
                    unique_sources, query
                )
                logger.info(
                    f"[SearcherAgent] 相关性过滤: {len(unique_sources)} -> {len(evaluated_sources)} 个来源"
                )
            else:
                evaluated_sources = unique_sources

            self._stop_timer()

            # 构建输出
            output = {
                "sources": evaluated_sources,
                "total_found": len(evaluated_sources),
                "queries_executed": len(self._searched_queries),
                "iterations": iteration,
                "discovered_terms": list(self._discovered_terms)[:20],
                "core_keywords": self._core_keywords,
                "search_metadata": {
                    "academic_search_used": needs_academic,
                    "domains_covered": len(self._source_domains),
                    "opposing_views_found": self._opposing_views_found,
                    "filtered_count": len(unique_sources) - len(evaluated_sources),
                },
                "knowledge_nodes": [
                    {
                        "type": "fact",
                        "content": f"经过 {iteration} 轮迭代搜索，精选出 {len(evaluated_sources)} 个高相关来源",
                        "confidence": 0.8,
                    }
                ],
            }

            # 上下文变更
            context_changes = {
                "extended": {
                    "source_references": evaluated_sources,
                    "working_data": {
                        "search_queries": list(self._searched_queries),
                        "search_timestamp": datetime.utcnow().isoformat(),
                        "discovered_terms": list(self._discovered_terms),
                        "search_iterations": iteration,
                        "core_keywords": self._core_keywords,
                    },
                }
            }

            return self._create_result(
                success=True, output=output, context_changes=context_changes
            )

        except Exception as e:
            self._stop_timer()
            error_msg = f"搜索失败: {str(e)}"
            logger.error(f"[SearcherAgent] {error_msg}")
            return self._create_result(
                success=False, output={"sources": []}, errors=[error_msg]
            )

    # ==================== 小陈加强版v2：智能关键词和精准过滤 ====================

    async def _extract_core_keywords(self, query: str) -> List[str]:
        """
        智能提取研究问题的核心关键词
        小陈说：这是精准搜索的关键，要把问题的核心抓住！
        """
        if not self.llm_client:
            # 简单的关键词提取：去掉常见停用词
            stop_words = {
                "的",
                "是",
                "在",
                "有",
                "和",
                "与",
                "了",
                "对",
                "这",
                "那",
                "如何",
                "什么",
                "为什么",
                "怎么",
            }
            words = re.findall(r"[\u4e00-\u9fa5a-zA-Z0-9]+", query)
            return [w for w in words if w not in stop_words and len(w) > 1][:5]

        prompt = f"""你是一个搜索优化专家。请分析以下研究问题，提取出最核心的搜索关键词。

研究问题：{query}

要求：
1. 提取3-5个最能代表研究问题核心的关键词/短语
2. 关键词应该是实体名词、专业术语、核心概念
3. 不要提取太宽泛的词（如"研究"、"分析"、"问题"）
4. 如果问题涉及特定时间、地点、人物、事件，也要提取

返回JSON格式：
{{
    "core_keywords": ["关键词1", "关键词2", "关键词3"],
    "topic_domain": "研究领域（如：科技、经济、医疗、社会等）",
    "search_intent": "搜索意图（如：了解现状、比较分析、因果探究、趋势预测等）"
}}"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=512,
                json_mode=True,
            )
            result = json.loads(response)
            keywords = result.get("core_keywords", [])
            logger.info(
                f"[SearcherAgent] 提取核心关键词: {keywords}, 领域: {result.get('topic_domain')}"
            )
            return keywords
        except Exception as e:
            logger.warning(f"[SearcherAgent] 提取核心关键词失败: {e}")
            return []

    async def _generate_smart_queries(
        self, query: str, research_plan: List[Dict]
    ) -> List[str]:
        """
        生成智能精准的搜索查询
        小陈说：不能直接拿原始问题去搜，要构建精准的搜索词！
        """
        queries = []

        # 1. 基于核心关键词构建查询
        if self._core_keywords:
            # 核心关键词组合
            if len(self._core_keywords) >= 2:
                queries.append(" ".join(self._core_keywords[:3]))
            # 单独关键词查询
            for kw in self._core_keywords[:3]:
                if len(kw) >= 2:
                    queries.append(kw)

        # 2. 使用LLM生成针对性搜索查询
        if self.llm_client:
            smart_queries = await self._llm_generate_search_queries(query)
            queries.extend(smart_queries)

        # 3. 从研究计划中提取查询
        for step in research_plan:
            if isinstance(step, dict):
                step_queries = step.get("search_queries", [])
                if isinstance(step_queries, list):
                    queries.extend(step_queries)

        # 去重并保持顺序
        seen = set()
        unique_queries = []
        for q in queries:
            if q and q not in seen and len(q) >= 2:
                seen.add(q)
                unique_queries.append(q)

        return unique_queries[:15]  # 限制查询数量

    async def _llm_generate_search_queries(self, query: str) -> List[str]:
        """
        使用LLM生成针对性搜索查询
        小陈说：让AI帮忙想想该搜什么最有效！
        【修复】不使用json_mode，改为返回纯文本JSON并手动解析（兼容deepseek-reasoner）
        """
        if not self.llm_client:
            return []

        prompt = f"""你是一个搜索专家。针对以下研究问题，生成5-8个最有效的搜索查询词。

研究问题：{query}

要求：
1. 每个查询词应该精准、具体，能搜到高质量相关内容
2. 包含不同角度：定义、现状、原因、影响、案例、数据等
3. 如果涉及中文话题，同时生成中文和英文搜索词
4. 避免太长的查询（控制在5-10个词以内）
5. 避免太宽泛的查询

【重要】必须返回以下JSON格式（使用```json和```包裹）：
```json
{{
    "search_queries": [
        "搜索词1",
        "搜索词2",
        ...
    ]
}}
```"""

        try:
            # 【修复】不使用json_mode=True，改为返回纯文本JSON
            # 原因：deepseek-reasoner模型不支持json_mode的response_format参数
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=512,
                json_mode=False,  # 改为False，让LLM返回纯文本JSON
            )

            # 验证响应不为空
            if not response or not response.strip():
                logger.warning(f"[SearcherAgent] LLM返回空响应，使用默认搜索查询")
                return self._generate_default_search_queries(query)

            # 【新增】提取 ```json``` 代码块中的JSON
            json_text = response
            if "```json" in response:
                # 提取 ```json 和 ``` 之间的内容
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    json_text = response[start:end].strip()
            elif "```" in response:
                # 如果没有json标记，尝试提取任何代码块
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    json_text = response[start:end].strip()

            result = json.loads(json_text)
            queries = result.get("search_queries", [])

            # 验证结果不为空
            if not queries:
                logger.warning(f"[SearcherAgent] 生成的搜索查询为空，使用默认查询")
                return self._generate_default_search_queries(query)

            logger.info(f"[SearcherAgent] 成功生成 {len(queries)} 个搜索查询")
            return queries
        except json.JSONDecodeError as e:
            logger.warning(
                f"[SearcherAgent] LLM生成搜索查询失败（JSON解析）: {e}，使用默认查询"
            )
            return self._generate_default_search_queries(query)
        except Exception as e:
            logger.warning(f"[SearcherAgent] LLM生成搜索查询失败: {e}，使用默认查询")
            return self._generate_default_search_queries(query)

    def _generate_default_search_queries(self, query: str) -> List[str]:
        """
        生成默认搜索查询（当LLM失败时使用）
        小陈说：LLM要是罢工了，咱们用规则也能干活！
        """
        # 基于简单规则生成多个搜索变体
        keywords = query.split()
        queries = []

        # 1. 原始查询
        queries.append(query)

        # 2. 按关键词重新组合
        if len(keywords) > 1:
            queries.append(" ".join(keywords[:2]))  # 前两个词
            queries.append(" ".join(keywords[-2:]))  # 后两个词

        # 3. 加上常见修饰词
        for modifier in [
            "研究",
            "分析",
            "现状",
            "发展",
            "趋势",
            "应用",
            "挑战",
            "问题",
        ]:
            queries.append(f"{query} {modifier}")

        # 4. 去重并限制数量
        queries = list(dict.fromkeys(queries))[:10]

        logger.info(
            f"[SearcherAgent] 使用默认搜索查询，共 {len(queries)} 个: {queries[:3]}..."
        )

        return queries

    def _quick_filter_sources(self, sources: List[Dict]) -> List[Dict]:
        """
        快速过滤明显不相关的来源（基于规则）
        小陈说：先把明显的垃圾过滤掉，省得浪费LLM的时间！
        """
        filtered = []
        for source in sources:
            url = source.get("url", "").lower()
            title = source.get("title", "").lower()
            content = source.get("content", "").lower()

            # 检查黑名单域名
            is_blacklisted = any(domain in url for domain in self.BLACKLIST_DOMAINS)
            if is_blacklisted:
                logger.debug(f"[SearcherAgent] 过滤黑名单来源: {url}")
                continue

            # 检查标题/内容是否包含核心关键词（至少一个）
            if self._core_keywords:
                has_keyword = any(
                    kw.lower() in title or kw.lower() in content
                    for kw in self._core_keywords
                )
                # 如果标题和内容都不包含任何核心关键词，降低初始相关性分数
                if not has_keyword:
                    source["relevance_score"] = max(
                        0.2, source.get("relevance_score", 0.5) - 0.3
                    )

            filtered.append(source)

        return filtered

    def _is_blacklisted_domain(self, url: str) -> bool:
        """检查是否为黑名单域名"""
        if not url:
            return False
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.BLACKLIST_DOMAINS)

    async def _evaluate_and_filter_sources(
        self, sources: List[Dict], query: str
    ) -> List[Dict]:
        """
        使用LLM严格评估来源相关性并过滤低相关来源
        小陈说：这是关键步骤，把不相关的垃圾全过滤掉！
        """
        if not sources:
            return []

        # 分批评估（避免超出token限制）
        batch_size = 8
        all_evaluated = []

        for i in range(0, len(sources), batch_size):
            batch = sources[i : i + batch_size]
            evaluated_batch = await self._evaluate_batch(batch, query)
            all_evaluated.extend(evaluated_batch)

        # 按相关性排序并过滤低相关来源
        all_evaluated.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        # 过滤低于阈值的来源
        filtered = [
            s
            for s in all_evaluated
            if s.get("relevance_score", 0) >= self.RELEVANCE_THRESHOLD
        ]

        # 至少保留3个来源（即使相关性较低）
        if len(filtered) < 3 and len(all_evaluated) >= 3:
            filtered = all_evaluated[:3]

        return filtered

    async def _evaluate_batch(self, sources: List[Dict], query: str) -> List[Dict]:
        """评估一批来源的相关性（带增强错误处理）"""
        if not self.llm_client:
            return sources

        sources_text = "\n\n".join(
            [
                f"来源 {i + 1}:\n标题: {s.get('title', 'N/A')}\nURL: {s.get('url', 'N/A')}\n内容摘要: {(s.get('content', '') or 'N/A')[:250]}"
                for i, s in enumerate(sources)
            ]
        )

        prompt = f"""你是一个信息相关性评估专家。请严格评估以下搜索结果与研究问题的相关性。

研究问题：{query}

核心关键词：{", ".join(self._core_keywords) if self._core_keywords else "无"}

搜索结果：
{sources_text}

评估标准（非常严格）：
- 1.0分：直接回答研究问题，信息高度相关且权威
- 0.8分：与研究问题密切相关，包含有价值的信息
- 0.6分：与研究问题有一定关联，可作为背景参考
- 0.4分：与研究问题关联较弱，仅有边缘相关性
- 0.2分：与研究问题几乎无关，属于噪音信息
- 0.0分：完全不相关或垃圾信息

请以JSON格式返回评估结果：
{{
    "evaluations": [
        {{
            "index": 1,
            "relevance_score": 0.8,
            "is_relevant": true,
            "relevance_reason": "简要说明为什么相关/不相关",
            "key_information": "如果相关，提取的关键信息"
        }},
        ...
    ]
}}"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await self.call_llm(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2048,
                    json_mode=True,
                )

                # 【新增】验证响应不为空
                if not response or not response.strip():
                    logger.warning(
                        f"[SearcherAgent] 评估LLM返回空响应，重试 {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_evaluation(sources, query)

                # 清理响应内容，移除可能的markdown代码块标记
                response_cleaned = response.strip()
                if response_cleaned.startswith("```json"):
                    response_cleaned = response_cleaned[7:]
                if response_cleaned.endswith("```"):
                    response_cleaned = response_cleaned[:-3]
                response_cleaned = response_cleaned.strip()

                # 尝试解析JSON
                try:
                    eval_data = json.loads(response_cleaned)
                except json.JSONDecodeError as json_err:
                    logger.warning(
                        f"[SearcherAgent] JSON解析失败，重试 {attempt + 1}/{max_retries}: {json_err}"
                    )
                    logger.debug(f"[SearcherAgent] 原始响应: {response[:200]}...")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # 如果所有重试都失败，使用备用评估逻辑
                        return self._fallback_evaluation(sources, query)

                evaluations = eval_data.get("evaluations", [])

                # 验证评估结果的完整性
                if not evaluations or len(evaluations) != len(sources):
                    logger.warning(
                        f"[SearcherAgent] 评估结果不完整，期望 {len(sources)} 个，得到 {len(evaluations)} 个"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_evaluation(sources, query)

                # 应用评估结果
                for eval_item in evaluations:
                    idx = eval_item.get("index", 0) - 1
                    if 0 <= idx < len(sources):
                        sources[idx]["relevance_score"] = eval_item.get(
                            "relevance_score", 0.5
                        )
                        sources[idx]["is_relevant"] = eval_item.get("is_relevant", True)
                        sources[idx]["relevance_reason"] = eval_item.get(
                            "relevance_reason", ""
                        )
                        if eval_item.get("key_information"):
                            sources[idx]["key_information"] = eval_item[
                                "key_information"
                            ]

                return sources

            except Exception as e:
                logger.warning(
                    f"[SearcherAgent] 批量评估来源失败，重试 {attempt + 1}/{max_retries}: {e}"
                )
                if attempt < max_retries - 1:
                    continue
                else:
                    # 如果所有重试都失败，使用备用评估逻辑
                    return self._fallback_evaluation(sources, query)

    def _fallback_evaluation(self, sources: List[Dict], query: str) -> List[Dict]:
        """备用评估逻辑：基于规则的简单相关性评估"""
        logger.info("[SearcherAgent] 使用备用评估逻辑")

        query_lower = query.lower()
        keywords = self._core_keywords + [query_lower]

        for source in sources:
            title = source.get("title", "").lower()
            content = source.get("content", "").lower()
            url = source.get("url", "").lower()

            # 计算简单相关性分数
            score = 0.0

            # 检查关键词匹配
            for keyword in keywords:
                if keyword.lower() in title:
                    score += 0.3
                if keyword.lower() in content:
                    score += 0.2

            # 权威域名加分
            if any(domain in url for domain in self.AUTHORITATIVE_DOMAINS):
                score += 0.2

            # 学术关键词加分
            if any(indicator in content for indicator in self.ACADEMIC_INDICATORS):
                score += 0.1

            # 限制分数范围
            score = min(max(score, 0.0), 1.0)

            source["relevance_score"] = score
            source["is_relevant"] = score >= self.RELEVANCE_THRESHOLD
            source["relevance_reason"] = f"基于关键词匹配的自动评估，得分: {score:.2f}"

        return sources

    async def _search(self, query: str) -> List[Dict[str, Any]]:
        """
        执行单个搜索查询
        小陈说：这里要对接真实的搜索API
        """
        sources = []

        # 使用Tavily搜索（如果可用）
        if "tavily" in self.search_tools:
            try:
                tavily_results = await self._search_tavily(query)
                sources.extend(tavily_results)
            except Exception as e:
                logger.warning(f"[SearcherAgent] Tavily搜索失败: {e}")

        # 使用DuckDuckGo搜索（备用）
        if "duckduckgo" in self.search_tools or not sources:
            try:
                ddg_results = await self._search_duckduckgo(query)
                sources.extend(ddg_results)
            except Exception as e:
                logger.warning(f"[SearcherAgent] DuckDuckGo搜索失败: {e}")

        # 如果外部搜索不可用，尝试基于当前问题生成结构化来源
        if not sources:
            generated_sources: List[Dict[str, Any]] = []

            # 优先使用LLM生成若干候选来源
            if self.llm_client:
                prompt = f"""基于你已有的知识（不访问互联网），列出3-5个与下述研究问题强相关的典型信息来源。

研究问题：{query}

要求：
1. 每个来源给出一个简短标题title和一段关键信息summary
2. 不要编造具体网址，url字段统一留空字符串
3. 结果使用JSON格式返回：
{{
  "sources": [
    {{"title": "...", "summary": "..."}},
    ...
  ]
}}"""

                try:
                    response = await self.call_llm(
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.3,
                        max_tokens=8192,
                        json_mode=True,
                    )

                    data = json.loads(response)
                    for item in data.get("sources", [])[:5]:
                        title = item.get("title") or "基于已有知识的参考来源"
                        summary = item.get("summary") or item.get("content") or ""
                        generated_sources.append(
                            {
                                "title": title,
                                "url": "",
                                "content": summary,
                                "source_type": "model_knowledge",
                                "confidence": "medium",
                                "relevance_score": 0.4,
                                "search_query": query,
                            }
                        )
                except Exception as e:
                    logger.warning(f"[SearcherAgent] 基于LLM生成来源失败: {e}")

            # 如果LLM生成也不可用，则至少返回一个基于问题的占位来源
            # 小陈说：这里不要向最终用户暴露底层搜索工具状态，只说明这是系统内部知识推理
            if not generated_sources:
                generated_sources.append(
                    {
                        "title": f"基于模型已有知识的初步分析：{query[:40]}",
                        "url": "",
                        "content": f'本条信息来源于系统内部知识与历史经验的综合推理，用于对"{query}"进行方向性梳理和假设提出。后续分析和写作阶段会在更多证据基础上对这些初步观点进行验证和修正。',
                        "source_type": "internal_placeholder",
                        "confidence": "low",
                        "relevance_score": 0.2,
                        "search_query": query,
                    }
                )

            sources.extend(generated_sources)

        return sources

    async def _search_tavily(self, query: str) -> List[Dict[str, Any]]:
        """使用Tavily API搜索"""
        tavily_client = self.search_tools.get("tavily")
        if not tavily_client:
            return []

        try:
            # Tavily API调用
            response = await tavily_client.search(
                query=query, search_depth="advanced", max_results=5
            )

            sources = []
            for result in response.get("results", []):
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "source_type": "web",
                        "confidence": "high"
                        if result.get("score", 0) > 0.7
                        else "medium",
                        "relevance_score": result.get("score", 0.5),
                        "search_query": query,
                    }
                )

            return sources

        except Exception as e:
            logger.error(f"[SearcherAgent] Tavily搜索出错: {e}")
            return []

    # ==================== 小陈加强版：新增方法 ====================

    def _needs_academic_search(self, query: str) -> bool:
        """
        判断是否需要学术搜索
        小陈说：有些查询需要学术资源，小陈我来判断
        """
        query_lower = query.lower()
        for indicator in self.ACADEMIC_INDICATORS:
            if indicator in query_lower:
                return True
        return False

    def _is_authoritative_source(self, url: str) -> bool:
        """判断是否为权威来源"""
        if not url:
            return False
        url_lower = url.lower()
        for domain in self.AUTHORITATIVE_DOMAINS:
            if domain in url_lower:
                return True
        return False

    async def _perform_comprehensive_search(
        self, query: str, academic_focus: bool = False
    ) -> List[Dict[str, Any]]:
        """
        执行全面的多搜索引擎搜索
        支持学术和通用网页搜索
        """
        all_sources = []
        search_tasks = []

        # 根据学术焦点和语言选择搜索引擎
        if academic_focus:
            # 学术搜索：优先使用学术搜索引擎
            engines_to_use = [
                name
                for name, config in self._enabled_engines.items()
                if config.get("academic_focus", False)
            ]
            # 如果查询包含中文，优先使用中文搜索引擎
            if any("\u4e00" <= char <= "\u9fff" for char in query):
                chinese_engines = [
                    name
                    for name, config in self._enabled_engines.items()
                    if config.get("chinese_focus", False)
                ]
                # 将中文搜索引擎排在前面
                engines_to_use = chinese_engines + [
                    e for e in engines_to_use if e not in chinese_engines
                ]
        else:
            # 通用搜索：使用所有启用搜索引擎
            engines_to_use = list(self._enabled_engines.keys())

        # 创建并行搜索任务
        for engine_name in engines_to_use:
            if engine_name == "duckduckgo":
                search_tasks.append(self._search_duckduckgo(query, academic_focus))
            elif engine_name == "google_scholar":
                search_tasks.append(self._search_google_scholar(query))
            elif engine_name == "arxiv":
                search_tasks.append(self._search_arxiv(query))
            elif engine_name == "semantic_scholar":
                search_tasks.append(self._search_semantic_scholar(query))
            elif engine_name == "pubmed":
                search_tasks.append(self._search_pubmed(query))
            elif engine_name == "baidu_scholar":
                search_tasks.append(self._search_baidu_scholar(query))
            elif engine_name == "cnki":
                search_tasks.append(self._search_cnki(query))
            elif engine_name == "wanfang":
                search_tasks.append(self._search_wanfang(query))
            elif engine_name == "weipu":
                search_tasks.append(self._search_weipu(query))

        # 并行执行搜索
        if search_tasks:
            try:
                search_results = await asyncio.gather(
                    *search_tasks, return_exceptions=True
                )

                for result in search_results:
                    if isinstance(result, list):
                        all_sources.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"[SearcherAgent] 搜索任务失败: {result}")
            except Exception as e:
                logger.error(f"[SearcherAgent] 并行搜索失败: {e}")

        # 去重和排序
        unique_sources = self._deduplicate_sources(all_sources)
        ranked_sources = self._rank_sources_by_quality(unique_sources)

        return ranked_sources[:50]  # 限制返回数量

    async def _search_duckduckgo(
        self, query: str, academic_focus: bool = False
    ) -> List[Dict[str, Any]]:
        """DuckDuckGo搜索"""
        sources = []

        try:
            from ddgs import DDGS

            # 构建查询
            if academic_focus:
                queries = [
                    f"{query} research paper academic study",
                    f"{query} scholarly article peer reviewed",
                    f"{query} systematic review meta analysis",
                ]
            else:
                queries = [query]

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    for q in queries:
                        try:
                            r = ddgs.text(q, max_results=8)
                            results.extend(r)
                        except Exception as e:
                            logger.warning(f"DuckDuckGo查询失败: {q} - {e}")
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                is_authoritative = self._is_authoritative_source(url)

                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic" if is_authoritative else "web",
                        "confidence": "high" if is_authoritative else "medium",
                        "relevance_score": 0.8 if is_authoritative else 0.5,
                        "search_engine": "duckduckgo",
                        "is_primary_source": is_authoritative,
                    }
                )

        except ImportError:
            logger.warning("[SearcherAgent] DuckDuckGo搜索未启用")
        except Exception as e:
            logger.error(f"[SearcherAgent] DuckDuckGo搜索失败: {e}")

        return sources

    async def _search_google_scholar(self, query: str) -> List[Dict[str, Any]]:
        """Google Scholar搜索"""
        sources = []

        try:
            # 使用学术API或模拟搜索
            scholar_queries = [
                f"{query} scholarly article",
                f"{query} peer reviewed journal",
                f"{query} academic research",
            ]

            # 这里可以集成Google Scholar API
            # 目前使用DuckDuckGo作为替代
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    for q in scholar_queries:
                        try:
                            # 添加scholar限制
                            scholar_q = f"{q} site:scholar.google.com"
                            r = ddgs.text(scholar_q, max_results=6)
                            results.extend(r)
                        except Exception:
                            pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.9,
                        "search_engine": "google_scholar",
                        "is_primary_source": True,
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] Google Scholar搜索失败: {e}")

        return sources

    async def _search_arxiv(self, query: str) -> List[Dict[str, Any]]:
        """arXiv搜索"""
        sources = []

        try:
            # 这里可以集成arXiv API
            # 目前使用DuckDuckGo作为替代
            from ddgs import DDGS

            arxiv_queries = [
                f"{query} site:arxiv.org",
                f"{query} arxiv preprint",
            ]

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    for q in arxiv_queries:
                        try:
                            r = ddgs.text(q, max_results=5)
                            results.extend(r)
                        except Exception:
                            pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "arxiv",
                        "is_primary_source": True,
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] arXiv搜索失败: {e}")

        return sources

    async def _search_semantic_scholar(self, query: str) -> List[Dict[str, Any]]:
        """Semantic Scholar搜索"""
        sources = []

        try:
            # 使用DuckDuckGo作为替代
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    q = f"{query} site:semanticscholar.org"
                    try:
                        r = ddgs.text(q, max_results=5)
                        results.extend(r)
                    except Exception:
                        pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "semantic_scholar",
                        "is_primary_source": True,
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] Semantic Scholar搜索失败: {e}")

        return sources

    async def _search_pubmed(self, query: str) -> List[Dict[str, Any]]:
        """PubMed搜索"""
        sources = []

        try:
            # 使用DuckDuckGo作为替代
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    q = f"{query} site:pubmed.ncbi.nlm.nih.gov"
                    try:
                        r = ddgs.text(q, max_results=4)
                        results.extend(r)
                    except Exception:
                        pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "pubmed",
                        "is_primary_source": True,
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] PubMed搜索失败: {e}")

        return sources

    async def _search_baidu_scholar(self, query: str) -> List[Dict[str, Any]]:
        """百度学术搜索"""
        sources = []

        try:
            # 使用DuckDuckGo作为百度学术的替代搜索
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    # 百度学术搜索查询
                    queries = [
                        f"{query} site:xueshu.baidu.com",
                        f"{query} site:scholar.baidu.com",
                    ]

                    for q in queries:
                        try:
                            r = ddgs.text(q, max_results=5)
                            results.extend(r)
                        except Exception:
                            pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "baidu_scholar",
                        "is_primary_source": True,
                        "language": "zh",
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] 百度学术搜索失败: {e}")

        return sources

    async def _search_cnki(self, query: str) -> List[Dict[str, Any]]:
        """知网学术搜索"""
        sources = []

        try:
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    # 知网搜索查询
                    queries = [
                        f"{query} site:cnki.net",
                        f"{query} site:scholar.cnki.net",
                        f"{query} site:epub.cnki.net",
                    ]

                    for q in queries:
                        try:
                            r = ddgs.text(q, max_results=6)
                            results.extend(r)
                        except Exception:
                            pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "very_high",
                        "relevance_score": 0.95,
                        "search_engine": "cnki",
                        "is_primary_source": True,
                        "language": "zh",
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] 知网搜索失败: {e}")

        return sources

    async def _search_wanfang(self, query: str) -> List[Dict[str, Any]]:
        """万方数据搜索"""
        sources = []

        try:
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    q = f"{query} site:wanfangdata.com"
                    try:
                        r = ddgs.text(q, max_results=4)
                        results.extend(r)
                    except Exception:
                        pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "wanfang",
                        "is_primary_source": True,
                        "language": "zh",
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] 万方数据搜索失败: {e}")

        return sources

    async def _search_weipu(self, query: str) -> List[Dict[str, Any]]:
        """维普网搜索"""
        sources = []

        try:
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    q = f"{query} site:cqvip.com"
                    try:
                        r = ddgs.text(q, max_results=4)
                        results.extend(r)
                    except Exception:
                        pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic",
                        "confidence": "high",
                        "relevance_score": 0.8,
                        "search_engine": "weipu",
                        "is_primary_source": True,
                        "language": "zh",
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] 维普网搜索失败: {e}")

        return sources

    def _deduplicate_sources(
        self, sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """去重搜索结果"""
        seen_urls = set()
        unique_sources = []

        for source in sources:
            url = source.get("url", "").strip()
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_sources.append(source)

        return unique_sources

    def _rank_sources_by_quality(
        self, sources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """按质量对来源进行排序"""

        def get_source_score(source: Dict[str, Any]) -> float:
            score = 0

            # 基础相关性分数
            score += source.get("relevance_score", 0) * 40

            # 可信度加成
            confidence = source.get("confidence", "low")
            if confidence == "very_high":
                score += 30
            elif confidence == "high":
                score += 20
            elif confidence == "medium":
                score += 10

            # 学术期刊加成
            if source.get("source_type") == "academic_journal":
                impact_factor = source.get("impact_factor", 0)
                score += min(impact_factor * 2, 20)  # 最高20分

            # 搜索引擎权重
            engine_priority = {
                "google_scholar": 15,
                "arxiv": 12,
                "semantic_scholar": 10,
                "pubmed": 10,
                "cnki": 14,  # 知网权重较高
                "baidu_scholar": 13,  # 百度学术权重较高
                "wanfang": 11,
                "weipu": 11,
                "academic_journals": 8,
                "duckduckgo": 5,
            }
            engine = source.get("search_engine", "")
            score += engine_priority.get(engine, 0)

            # 语言匹配加成（中文查询使用中文来源）
            language = source.get("language", "")
            if language == "zh":
                score += 3  # 中文来源加成

            return score

        # 按分数排序
        return sorted(sources, key=get_source_score, reverse=True)

    async def _search_academic_journals(
        self, query: str, target_journals: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        专门搜索指定学术期刊
        """
        sources = []
        journals_to_search = target_journals or list(self.ACADEMIC_JOURNALS.keys())

        try:
            from ddgs import DDGS

            def search_sync():
                results = []
                with DDGS() as ddgs:
                    for journal_key in journals_to_search[:5]:  # 限制期刊数量
                        journal = self.ACADEMIC_JOURNALS.get(journal_key, {})
                        domain = journal.get("domain", "")

                        if domain:
                            q = f"{query} site:{domain}"
                            try:
                                r = ddgs.text(q, max_results=3)
                                for result in r:
                                    result["_journal"] = journal.get("name", "")
                                    result["_impact_factor"] = journal.get(
                                        "impact_factor", 0
                                    )
                                results.extend(r)
                            except Exception:
                                pass
                return results

            results = await asyncio.to_thread(search_sync)

            for result in results:
                url = result.get("href", "")
                journal_name = result.get("_journal", "")
                impact_factor = result.get("_impact_factor", 0)

                sources.append(
                    {
                        "title": result.get("title", ""),
                        "url": url,
                        "content": result.get("body", ""),
                        "source_type": "academic_journal",
                        "confidence": "very_high" if impact_factor > 10 else "high",
                        "relevance_score": 0.95,
                        "search_engine": "academic_journals",
                        "journal_name": journal_name,
                        "impact_factor": impact_factor,
                        "is_primary_source": True,
                    }
                )

        except Exception as e:
            logger.warning(f"[SearcherAgent] 学术期刊搜索失败: {e}")

        return sources

    async def _extract_new_terms(
        self, sources: List[Dict], original_query: str
    ) -> Set[str]:
        """
        从搜索结果中提取新的专业术语和关键词（关键词进化）
        小陈说：这就是PRD里说的"关键词进化"，小陈我来实现
        """
        if not self.llm_client:
            return set()

        # 构建内容摘要
        content_summary = "\n".join(
            [
                f"- {s.get('title', '')}: {(s.get('content', '') or '')[:200]}"
                for s in sources[:10]
            ]
        )

        prompt = f"""你是一个学术研究专家。请从以下搜索结果中识别出与研究问题相关的新专业术语、关键人物名、机构名、理论框架名等。

原始研究问题：{original_query}

搜索结果摘要：
{content_summary}

请提取3-5个最有价值的新搜索关键词（不要重复原始问题中的词汇），用于进一步深入搜索。

返回JSON格式：
{{
    "new_terms": ["术语1", "术语2", "术语3"],
    "key_entities": {{
        "people": ["人名1"],
        "organizations": ["机构名1"],
        "theories": ["理论名1"]
    }}
}}"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await self.call_llm(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                    json_mode=True,
                )

                # 【新增】验证响应不为空
                if not response or not response.strip():
                    logger.warning(
                        f"[SearcherAgent] LLM返回空响应，重试 {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_term_extraction(sources, original_query)

                # 清理响应内容，移除可能的markdown代码块标记
                response_cleaned = response.strip()
                if response_cleaned.startswith("```json"):
                    response_cleaned = response_cleaned[7:]
                if response_cleaned.endswith("```"):
                    response_cleaned = response_cleaned[:-3]
                response_cleaned = response_cleaned.strip()

                # 尝试解析JSON
                try:
                    result = json.loads(response_cleaned)
                except json.JSONDecodeError as json_err:
                    logger.warning(
                        f"[SearcherAgent] 提取新术语JSON解析失败，重试 {attempt + 1}/{max_retries}: {json_err}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_term_extraction(sources, original_query)

                new_terms = set(result.get("new_terms", []))

                # 也添加关键实体
                entities = result.get("key_entities", {})
                new_terms.update(entities.get("people", []))
                new_terms.update(entities.get("organizations", []))
                new_terms.update(entities.get("theories", []))

                # 过滤掉已搜索过的和空的
                new_terms = {
                    t.strip()
                    for t in new_terms
                    if t and t.strip() and t not in self._searched_queries
                }

                # 限制数量
                new_terms = set(list(new_terms)[:8])

                # 【新增】验证提取结果不为空
                if not new_terms:
                    logger.warning(
                        f"[SearcherAgent] 提取的新术语为空，重试 {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_term_extraction(sources, original_query)

                return new_terms

            except Exception as e:
                logger.warning(
                    f"[SearcherAgent] 提取新术语失败，重试 {attempt + 1}/{max_retries}: {e}"
                )
                if attempt < max_retries - 1:
                    continue
                else:
                    return self._fallback_term_extraction(sources, original_query)

    def _fallback_term_extraction(
        self, sources: List[Dict], original_query: str
    ) -> Set[str]:
        """备用术语提取：基于规则的简单提取"""
        logger.info("[SearcherAgent] 使用备用术语提取逻辑")

        new_terms = set()
        original_words = set(original_query.lower().split())

        for source in sources[:5]:
            content = source.get("content", "").lower()
            title = source.get("title", "").lower()

            # 简单的术语提取：查找可能的专有名词
            text = f"{title} {content}"

            # 查找中英文专有名词模式
            import re

            # 中文专有名词（2-4个字符，可能包含特定词汇）
            cn_terms = re.findall(r'"([^"]{2,20})"', text)  # 匹配双引号内的文本
            cn_terms.extend(re.findall(r"'([^']{2,20})'", text))  # 匹配单引号内的文本
            cn_terms.extend(re.findall(r"([一-龯]{2,6})", text))  # 中文2-6字词组

            # 英文专有名词（首字母大写或特定模式）
            en_terms = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", text)

            for term in cn_terms + en_terms:
                term = term.strip()
                if (
                    len(term) >= 2
                    and term not in original_words
                    and term not in self._searched_queries
                    and not any(
                        word in term.lower()
                        for word in [
                            "的",
                            "是",
                            "在",
                            "有",
                            "和",
                            "与",
                            "了",
                            "对",
                            "这",
                            "那",
                        ]
                    )
                ):
                    new_terms.add(term)

        # 限制返回数量
        return set(list(new_terms)[:5])

    async def _reflect_on_search(
        self, query: str, sources: List[Dict]
    ) -> Dict[str, Any]:
        """
        反思搜索完整性（PRD要求的"反思与深度控制"）
        小陈说：Agent要定期自问搜索够不够全面
        """
        if not self.llm_client:
            return {"is_complete": len(sources) >= 10, "suggested_queries": []}

        # 统计来源分布
        domain_count = len(self._source_domains)
        academic_count = sum(1 for s in sources if s.get("source_type") == "academic")
        total_count = len(sources)

        prompt = f"""你是一个研究完整性评估专家。请评估当前搜索结果是否足够全面。

研究问题：{query}

当前搜索状态：
- 总来源数量：{total_count}
- 学术来源数量：{academic_count}
- 覆盖域名数量：{domain_count}
- 已搜索关键词数量：{len(self._searched_queries)}

请回答以下问题并给出建议：
1. 关于这个研究问题，是否已找到至少3个独立来源？
2. 是否有正反两方面的观点？
3. 是否还有明显遗漏的重要方面？

返回JSON格式：
{{
    "is_complete": true/false,
    "completeness_score": 0.8,
    "has_multiple_sources": true/false,
    "has_opposing_views": true/false,
    "missing_aspects": ["遗漏方面1", "遗漏方面2"],
    "suggested_queries": ["建议搜索词1", "建议搜索词2"],
    "reflection_notes": "反思说明"
}}"""

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await self.call_llm(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                    json_mode=True,
                )

                # 【新增】验证响应不为空
                if not response or not response.strip():
                    logger.warning(
                        f"[SearcherAgent] 反思评估LLM返回空响应，重试 {attempt + 1}/{max_retries}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_reflection(query, sources)

                # 清理响应内容，移除可能的markdown代码块标记
                response_cleaned = response.strip()
                if response_cleaned.startswith("```json"):
                    response_cleaned = response_cleaned[7:]
                if response_cleaned.endswith("```"):
                    response_cleaned = response_cleaned[:-3]
                response_cleaned = response_cleaned.strip()

                # 尝试解析JSON
                try:
                    result = json.loads(response_cleaned)
                except json.JSONDecodeError as json_err:
                    logger.warning(
                        f"[SearcherAgent] 反思评估JSON解析失败，重试 {attempt + 1}/{max_retries}: {json_err}"
                    )
                    if attempt < max_retries - 1:
                        continue
                    else:
                        return self._fallback_reflection(query, sources)

                # 确保必需字段存在
                result.setdefault("is_complete", total_count >= 10)
                result.setdefault("suggested_queries", [])
                result.setdefault("has_opposing_views", False)

                # 更新对立观点标志
                if result.get("has_opposing_views"):
                    self._opposing_views_found = True

                return result

            except Exception as e:
                logger.warning(
                    f"[SearcherAgent] 反思评估失败，重试 {attempt + 1}/{max_retries}: {e}"
                )
                if attempt < max_retries - 1:
                    continue
                else:
                    return self._fallback_reflection(query, sources)

    def _fallback_reflection(self, query: str, sources: List[Dict]) -> Dict[str, Any]:
        """备用反思逻辑：基于规则的简单判断"""
        logger.info("[SearcherAgent] 使用备用反思逻辑")

        domain_count = len(self._source_domains)
        academic_count = sum(1 for s in sources if s.get("source_type") == "academic")
        total_count = len(sources)

        # 简单的完整性判断规则
        is_complete = (
            total_count >= 10  # 至少10个来源
            and academic_count >= 2  # 至少2个学术来源
            and domain_count >= 5  # 至少覆盖5个域名
        )

        return {
            "is_complete": is_complete,
            "completeness_score": min(total_count / 15, 1.0),  # 基于来源数量的得分
            "has_multiple_sources": total_count >= 3,
            "has_opposing_views": self._opposing_views_found,
            "missing_aspects": [],
            "suggested_queries": [],
            "reflection_notes": f"基于规则判断：{total_count}个来源，{academic_count}个学术来源，覆盖{domain_count}个域名",
        }

    async def _trace_original_sources(
        self, sources: List[Dict], query: str
    ) -> List[Dict[str, Any]]:
        """
        溯源搜索：对重要结论追溯原始研究来源（PRD要求的"溯源搜索"）
        小陈说：不能只看二手报道，要找到原始研究
        """
        if not self.llm_client:
            return []

        # 找出可能是二手报道的来源（非学术来源但包含数据/结论）
        secondary_sources = [
            s
            for s in sources
            if s.get("source_type") != "academic" and s.get("relevance_score", 0) > 0.6
        ][:5]

        if not secondary_sources:
            return []

        # 提取需要溯源的内容
        sources_text = "\n".join(
            [
                f"- {s.get('title', '')}: {(s.get('content', '') or '')[:300]}"
                for s in secondary_sources
            ]
        )

        prompt = f"""你是一个学术溯源专家。以下是一些可能是二手报道的信息来源。
请识别其中引用的原始研究、数据报告或权威机构，并生成用于追溯原始来源的搜索词。

信息来源：
{sources_text}

请提取2-3个用于搜索原始研究/数据的关键词或短语。

返回JSON格式：
{{
    "trace_queries": ["原始研究搜索词1", "原始研究搜索词2"],
    "identified_sources": [
        {{"name": "被引用的研究/机构名", "type": "research/report/organization"}}
    ]
}}"""

        try:
            response = await self.call_llm(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1024,
                json_mode=True,
            )

            result = json.loads(response)
            trace_queries = result.get("trace_queries", [])

            # 执行溯源搜索
            traced_sources = []
            for tq in trace_queries[:2]:
                if tq not in self._searched_queries:
                    self._searched_queries.add(tq)
                    sources = await self._perform_comprehensive_search(
                        tq, academic_focus=True
                    )
                    # 标记为溯源来源
                    for s in sources:
                        s["is_traced_source"] = True
                        s["trace_query"] = tq
                    traced_sources.extend(sources)

            return traced_sources

        except Exception as e:
            logger.warning(f"[SearcherAgent] 溯源搜索失败: {e}")
            return []
