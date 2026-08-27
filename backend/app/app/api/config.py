"""
backend/app/api/config.py
──────────────────────────
Environment-based settings for Member E's API layer.
All mock/real switches live here — changing USE_MOCK_GRAPH or USE_MOCK_RAG
to false is the only change required to plug in C/D or B's real modules.
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    app_env: str = "development"
    secret_key: str = "INSECURE_DEV_KEY_change_in_production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Mock/Real switches (INTERFACES.md §6/§7)
    use_mock_graph: bool = True
    use_mock_rag: bool = True

    # Database (Member A will provide real Postgres URL)
    db_backend: str = "sqlite"
    sqlite_path: str = "./courtroom_dev.db"
    database_url: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # File uploads
    upload_dir: str = "./uploads"
    max_upload_size_mb: int = 25

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    # Public search APIs
    courtlistener_api_key: str = ""
    govinfo_api_key: str = ""

    # n8n internal service token (NOT a user JWT)
    n8n_service_token: str = "INSECURE_N8N_TOKEN_change_in_production"

    # Frontend URL
    frontend_url: str = "http://localhost:5173"

    # Algorithm for JWT
    algorithm: str = "HS256"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
