"""Adapter settings — Dify base URL + model_id → app API key map."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    dify_base_url: str = Field(
        default="http://127.0.0.1/v1",
        description="Dify Service API base, including /v1",
    )
    # JSON object: {"marketing-agent": "app-xxx", "dev-agent": "app-yyy"}
    # Or leave empty and use agents_file instead.
    dify_agents_json: str = Field(default="", alias="DIFY_AGENTS")
    # Optional path to JSON file with the same shape (preferred for secrets).
    agents_file: str = Field(default="agents.json")

    adapter_host: str = "127.0.0.1"
    adapter_port: int = 8085

    @field_validator("dify_base_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    def agent_map(self) -> dict[str, str]:
        """Return model_id → Dify app API key."""
        merged: dict[str, str] = {}

        path = Path(self.agents_file)
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError(f"{path} must be a JSON object")
            merged.update({str(k): str(v) for k, v in data.items()})

        raw = (self.dify_agents_json or "").strip()
        if raw:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("DIFY_AGENTS must be a JSON object")
            merged.update({str(k): str(v) for k, v in data.items()})

        return merged

    def api_key_for_model(self, model_id: str) -> str | None:
        return self.agent_map().get(model_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
