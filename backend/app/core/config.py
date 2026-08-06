from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Traceveil"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./data/traceveil.db"
    frontend_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen9b-q4_k_m"
    ollama_timeout_seconds: float = Field(default=2.0, gt=0)
    max_evidence_file_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    max_validation_issues: int = Field(default=100, gt=0)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_frontend_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
