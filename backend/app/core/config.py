"""
应用配置文件
小陈出品，配置都在这里，别tm到处找
支持国内外主流大模型！
"""

from typing import Optional, List
from pathlib import Path
import json
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用设置，这个类管理所有配置项"""

    # 应用基础配置
    APP_NAME: str = "DeepResearch Pro"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 服务器配置
    HOST: str = "127.0.0.1"
    PORT: int = 8000  # 统一使用8000端口，与Vite代理保持一致

    # 数据库配置 - SQLite，简单够用
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/research.db"

    # ChromaDB 向量数据库配置
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # ==================== LLM 配置（支持国内外大模型） ====================
    # 提供商：openai, qwen, zhipu, moonshot, deepseek, yi, baichuan, minimax, custom
    LLM_PROVIDER: str = "openai"

    # API Key（必填）
    LLM_API_KEY: Optional[str] = None

    # API Base URL（可选，不填则使用提供商默认地址）
    # 常用地址：
    # - OpenAI: https://api.openai.com/v1
    # - 通义千问: https://dashscope.aliyuncs.com/compatible-mode/v1
    # - 智谱AI: https://open.bigmodel.cn/api/paas/v4
    # - 月之暗面: https://api.moonshot.cn/v1
    # - DeepSeek: https://api.deepseek.com/v1
    # - 零一万物: https://api.lingyiwanwu.com/v1
    # - 百川: https://api.baichuan-ai.com/v1
    # - MiniMax: https://api.minimax.chat/v1
    LLM_BASE_URL: Optional[str] = None

    # 模型名称（可选，不填则使用提供商默认模型）
    # 常用模型：
    # - OpenAI: gpt-4o, gpt-4o-mini, gpt-4-turbo
    # - 通义千问: qwen-turbo, qwen-plus, qwen-max
    # - 智谱AI: glm-4, glm-4-flash, glm-3-turbo
    # - 月之暗面: moonshot-v1-8k, moonshot-v1-32k, moonshot-v1-128k
    # - DeepSeek: deepseek-chat, deepseek-coder
    # - 零一万物: yi-large, yi-medium
    # - 百川: Baichuan4, Baichuan3-Turbo
    # - MiniMax: abab6.5s-chat, abab5.5-chat
    LLM_MODEL: Optional[str] = None

    # 兼容旧配置（向后兼容）
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ==================== 搜索配置 ====================
    MAX_SEARCH_RESULTS: int = 10
    SEARCH_TIMEOUT: int = 30

    # WebSocket 配置
    WS_HEARTBEAT_INTERVAL: int = 30

    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    def get_llm_config(self) -> dict:
        """
        获取 LLM 配置
        小陈说：这个方法统一处理新旧配置，优先使用新配置
        """
        local_overrides = _read_local_llm_config()

        api_key = local_overrides.get("api_key")
        base_url = local_overrides.get("base_url")
        model = local_overrides.get("model")
        provider = local_overrides.get("provider")

        if api_key is None:
            api_key = self.LLM_API_KEY or self.OPENAI_API_KEY
        if base_url is None:
            base_url = self.LLM_BASE_URL or self.OPENAI_BASE_URL
        if model is None:
            model = self.LLM_MODEL or self.OPENAI_MODEL
        if provider is None:
            provider = self.LLM_PROVIDER

        # 如果只配置了 OPENAI_API_KEY，自动设置 provider 为 openai
        if not self.LLM_API_KEY and self.OPENAI_API_KEY:
            provider = "openai"

        return {
            "provider": provider,
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
        }

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # 忽略额外的配置项，避免验证错误


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    小陈我用lru_cache缓存，别每次都创建新的，浪费资源
    """
    return Settings()


# 导出配置实例
settings = get_settings()


def _read_local_llm_config() -> dict:
    path = Path("data") / "llm_config.json"
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}

        def normalize(value: object) -> Optional[str]:
            if value is None:
                return None
            if isinstance(value, str):
                v = value.strip()
                return v if v else None
            return None

        return {
            "provider": normalize(raw.get("provider")),
            "api_key": normalize(raw.get("api_key")),
            "base_url": normalize(raw.get("base_url")),
            "model": normalize(raw.get("model")),
        }
    except Exception:
        return {}
