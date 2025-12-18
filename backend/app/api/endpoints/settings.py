from pathlib import Path
import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.core.llm_factory import LLMFactory


router = APIRouter()


class LLMConfigPublic(BaseModel):
    provider: str
    base_url: str | None = None
    model: str | None = None
    api_key_set: bool
    api_key_last4: str | None = None


class LLMConfigUpdate(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


def _config_path() -> Path:
    return Path("data") / "llm_config.json"


def _read_config_file() -> dict:
    path = _config_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _write_config_file(data: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_public(config: dict) -> LLMConfigPublic:
    api_key = config.get("api_key")
    last4 = api_key[-4:] if isinstance(api_key, str) and len(api_key) >= 4 else None
    return LLMConfigPublic(
        provider=str(config.get("provider") or "openai"),
        base_url=config.get("base_url"),
        model=config.get("model"),
        api_key_set=bool(api_key),
        api_key_last4=last4,
    )


@router.get("/llm/providers")
async def list_llm_providers():
    return LLMFactory.get_supported_providers()


@router.get("/llm", response_model=LLMConfigPublic)
async def get_llm_config():
    return _to_public(settings.get_llm_config())


@router.put("/llm", response_model=LLMConfigPublic)
async def update_llm_config(payload: LLMConfigUpdate):
    existing = _read_config_file()

    def normalize(value: str | None) -> str | None:
        if value is None:
            return None
        v = value.strip()
        return v if v else None

    next_data = {
        "provider": normalize(payload.provider) or existing.get("provider") or "openai",
        "base_url": normalize(payload.base_url)
        if payload.base_url is not None
        else existing.get("base_url"),
        "model": normalize(payload.model)
        if payload.model is not None
        else existing.get("model"),
        "api_key": normalize(payload.api_key)
        if payload.api_key is not None
        else existing.get("api_key"),
    }

    _write_config_file(next_data)
    return _to_public(settings.get_llm_config())

