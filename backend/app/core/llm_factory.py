"""
LLM工厂类 - 统一管理国内外主流大模型

支持的大模型包括：
- OpenAI系列
- Anthropic Claude系列
- Google Gemini系列
- 国内各大模型提供商

大部分模型兼容OpenAI API格式，可直接使用OpenAI SDK调用
"""

from typing import Optional, Dict, Any, List
from enum import Enum
from dataclasses import dataclass

from openai import AsyncOpenAI

from app.core.logging import logger


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""

    # 国际
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"

    # 国内
    QWEN = "qwen"  # 阿里通义千问
    WENXIN = "wenxin"  # 百度文心
    ZHIPU = "zhipu"  # 智谱AI
    MOONSHOT = "moonshot"  # 月之暗面
    SPARK = "spark"  # 讯飞星火
    YI = "yi"  # 零一万物
    DEEPSEEK = "deepseek"  # 深度求索
    BAICHUAN = "baichuan"  # 百川智能
    MINIMAX = "minimax"  # MiniMax

    # 自定义 OpenAI 兼容接口
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM 配置信息"""

    provider: LLMProvider
    api_key: str
    base_url: Optional[str] = None
    model: str = ""
    default_model: str = ""

    # 模型别名映射
    model_aliases: Dict[str, str] = None

    def __post_init__(self):
        if self.model_aliases is None:
            self.model_aliases = {}


# 各大模型提供商的默认配置
PROVIDER_CONFIGS: Dict[LLMProvider, Dict[str, Any]] = {
    # ==================== 国际大模型 ====================
    LLMProvider.OPENAI: {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "o1",
            "o1-mini",
            "o1-preview",
        ],
    },
    LLMProvider.ANTHROPIC: {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-3-5-sonnet-20241022",
        "models": [
            "claude-3-opus-20240229",
            "claude-3-5-sonnet-20241022",
            "claude-3-haiku-20240307",
        ],
        # Anthropic 需要特殊处理，但也可以通过兼容层调用
    },
    LLMProvider.GOOGLE: {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-1.5-pro",
        "models": ["gemini-pro", "gemini-1.5-pro", "gemini-1.5-flash"],
    },
    # ==================== 国内大模型 ====================
    LLMProvider.QWEN: {
        # 阿里通义千问 - 兼容 OpenAI API
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "models": [
            "qwen-turbo",
            "qwen-plus",
            "qwen-max",
            "qwen-max-longcontext",
            "qwen-long",
        ],
    },
    LLMProvider.ZHIPU: {
        # 智谱AI - 兼容 OpenAI API
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "default_model": "glm-4-flash",
        "models": ["glm-4", "glm-4-flash", "glm-4-plus", "glm-4-long", "glm-3-turbo"],
    },
    LLMProvider.MOONSHOT: {
        # 月之暗面 Kimi - 兼容 OpenAI API
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
    LLMProvider.DEEPSEEK: {
        # 深度求索 - 兼容 OpenAI API
        # 小陈说：用deepseek-chat作为默认，速度快，api兼容好
        # 如果需要推理，可选deepseek-reasoner（但推理不支持json_mode）
        "base_url": "https://api.deepseek.com/v1",  # 改为标准v1 API
        "default_model": "deepseek-chat",  # 改为deepseek-chat
        "models": [
            "deepseek-chat",
            "deepseek-coder",
            "deepseek-reasoner",
        ],  # 删除了V3.2-Speciale
    },
    LLMProvider.YI: {
        # 零一万物 - 兼容 OpenAI API
        "base_url": "https://api.lingyiwanwu.com/v1",
        "default_model": "yi-large",
        "models": ["yi-large", "yi-medium", "yi-spark", "yi-large-turbo"],
    },
    LLMProvider.BAICHUAN: {
        # 百川智能 - 兼容 OpenAI API
        "base_url": "https://api.baichuan-ai.com/v1",
        "default_model": "Baichuan4",
        "models": ["Baichuan4", "Baichuan3-Turbo", "Baichuan2-Turbo"],
    },
    LLMProvider.MINIMAX: {
        # MiniMax - 兼容 OpenAI API
        "base_url": "https://api.minimax.chat/v1",
        "default_model": "abab6.5s-chat",
        "models": ["abab6.5s-chat", "abab6.5g-chat", "abab5.5-chat"],
    },
    LLMProvider.WENXIN: {
        # 百度文心一言 - 需要特殊处理（有兼容层）
        "base_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop",
        "default_model": "ernie-4.0-8k",
        "models": ["ernie-4.0-8k", "ernie-3.5-8k", "ernie-speed-8k"],
        "note": "文心需要特殊的access_token机制，建议使用第三方兼容层",
    },
    LLMProvider.SPARK: {
        # 讯飞星火 - 需要特殊处理（有兼容层）
        "base_url": "https://spark-api-open.xf-yun.com/v1",
        "default_model": "generalv3.5",
        "models": ["generalv3.5", "generalv3", "generalv2"],
        "note": "星火需要APPID/APIKey/APISecret三个参数",
    },
    LLMProvider.CUSTOM: {
        # 自定义 OpenAI 兼容接口（如本地部署的 Ollama, vLLM 等）
        "base_url": "",
        "default_model": "",
        "models": [],
    },
}


class LLMFactory:
    """
    LLM 客户端工厂类
    小陈说：这玩意儿负责创建和管理各种大模型客户端

    使用方法：
    ```python
    factory = LLMFactory()

    # 使用配置初始化
    factory.configure(
        provider="qwen",
        api_key="sk-xxx",
        model="qwen-plus"
    )

    # 获取客户端
    client = factory.get_client()
    model = factory.get_model()

    # 调用
    response = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "你好"}]
    )
    ```
    """

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._config: Optional[LLMConfig] = None
        self._provider: Optional[LLMProvider] = None

    def configure(
        self,
        provider: str,
        api_key: str,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        """
        配置 LLM 客户端

        Args:
            provider: 提供商名称（openai, qwen, zhipu, moonshot, deepseek 等）
            api_key: API 密钥
            base_url: 自定义 API 地址（可选，默认使用提供商默认地址）
            model: 模型名称（可选，默认使用提供商默认模型）
        """
        # 解析提供商
        try:
            self._provider = LLMProvider(provider.lower())
        except ValueError:
            # 未知提供商，使用自定义模式
            logger.warning(f"[LLMFactory] 未知提供商: {provider}，使用自定义模式")
            self._provider = LLMProvider.CUSTOM

        # 获取提供商默认配置
        provider_config = PROVIDER_CONFIGS.get(self._provider, {})

        # 构建配置
        self._config = LLMConfig(
            provider=self._provider,
            api_key=api_key,
            base_url=base_url or provider_config.get("base_url"),
            model=model or provider_config.get("default_model", ""),
            default_model=provider_config.get("default_model", ""),
        )

        # 创建客户端
        self._create_client()

        logger.info(
            f"[LLMFactory] 配置完成: provider={self._provider.value}, "
            f"base_url={self._config.base_url}, model={self._config.model}"
        )

    def _create_client(self) -> None:
        """创建 OpenAI 兼容客户端"""
        if not self._config:
            raise ValueError("请先调用 configure() 方法配置 LLM")

        if not self._config.api_key:
            raise ValueError("API Key 不能为空")

        # 大部分国内大模型都兼容 OpenAI API，直接用 openai SDK
        self._client = AsyncOpenAI(
            api_key=self._config.api_key,
            base_url=self._config.base_url,
        )

    def get_client(self) -> AsyncOpenAI:
        """获取 LLM 客户端"""
        if not self._client:
            raise ValueError("请先调用 configure() 方法配置 LLM")
        return self._client

    def get_model(self) -> str:
        """获取当前配置的模型名称"""
        if not self._config:
            raise ValueError("请先调用 configure() 方法配置 LLM")
        return self._config.model

    def get_provider(self) -> Optional[LLMProvider]:
        """获取当前提供商"""
        return self._provider

    def is_configured(self) -> bool:
        """检查是否已配置"""
        return self._client is not None and self._config is not None

    @staticmethod
    def get_supported_providers() -> List[Dict[str, Any]]:
        """
        获取所有支持的提供商列表
        小陈说：前端可以用这个接口展示支持的大模型列表
        """
        result = []
        for provider, config in PROVIDER_CONFIGS.items():
            result.append(
                {
                    "id": provider.value,
                    "name": _get_provider_display_name(provider),
                    "base_url": config.get("base_url", ""),
                    "default_model": config.get("default_model", ""),
                    "models": config.get("models", []),
                    "note": config.get("note", ""),
                }
            )
        return result

    @staticmethod
    def get_provider_models(provider: str) -> List[str]:
        """获取指定提供商支持的模型列表"""
        try:
            p = LLMProvider(provider.lower())
            return PROVIDER_CONFIGS.get(p, {}).get("models", [])
        except ValueError:
            return []


def _get_provider_display_name(provider: LLMProvider) -> str:
    """获取提供商显示名称"""
    names = {
        LLMProvider.OPENAI: "OpenAI",
        LLMProvider.ANTHROPIC: "Anthropic Claude",
        LLMProvider.GOOGLE: "Google Gemini",
        LLMProvider.QWEN: "阿里通义千问",
        LLMProvider.WENXIN: "百度文心一言",
        LLMProvider.ZHIPU: "智谱AI ChatGLM",
        LLMProvider.MOONSHOT: "月之暗面 Kimi",
        LLMProvider.SPARK: "讯飞星火",
        LLMProvider.YI: "零一万物",
        LLMProvider.DEEPSEEK: "深度求索 DeepSeek",
        LLMProvider.BAICHUAN: "百川智能",
        LLMProvider.MINIMAX: "MiniMax",
        LLMProvider.CUSTOM: "自定义 OpenAI 兼容接口",
    }
    return names.get(provider, provider.value)


# 全局 LLM 工厂实例
_llm_factory: Optional[LLMFactory] = None


def get_llm_factory() -> LLMFactory:
    """
    获取全局 LLM 工厂实例
    小陈说：单例模式，全局共享一个工厂
    """
    global _llm_factory
    if _llm_factory is None:
        _llm_factory = LLMFactory()
    return _llm_factory


def configure_llm(
    provider: str,
    api_key: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMFactory:
    """
    配置全局 LLM 客户端
    小陈说：应用启动时调用这个方法初始化 LLM
    """
    factory = get_llm_factory()
    factory.configure(provider, api_key, base_url, model)
    return factory
