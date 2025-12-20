"""
应用配置文件
"""

from typing import Optional, List
from pathlib import Path
import json
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """应用设置类"""

    # 应用基础配置
    APP_NAME: str = "DeepResearch Pro"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # 服务器配置
    HOST: str = "127.0.0.1"
    PORT: int = 1031  # 逆变器专用端口

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/research.db"

    # ChromaDB配置
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # LLM配置
    LLM_PROVIDER: str = "openai"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
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

    # 服务器配置
    HOST: str = "0.0.0.0"  # 修改为0.0.0.0，允许监听所有网络接口
    PORT: int = 1031  # 逆变器专用端口

    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    def get_llm_config(self) -> dict:
        """获取LLM配置"""
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
    """获取配置单例"""
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
