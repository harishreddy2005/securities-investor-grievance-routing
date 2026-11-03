from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    redis_url: str = "redis://localhost:6379/0"
    queue_name: str = "grievances"
    index_dir: Path = Path("data/index")
    corpus_dir: Path = Path("corpus/raw")
    embedding_provider: str = "chroma"
    embedding_cache_dir: Path = Path("data/models")
    llm_provider: str = "stub"
    llm_stub_url: str = "http://localhost:8001"
    job_timeout: int = 180
    result_ttl: int = 604800
    llm_timeout: float = Field(default=10, gt=0, le=60)
    retrieval_timeout: float = Field(default=15, gt=0, le=60)
    redis_timeout: float = Field(default=3, gt=0, le=15)
    dependency_retries: int = Field(default=2, ge=0, le=3)
    retry_base_seconds: float = Field(default=0.2, ge=0, le=5)
    retry_cap_seconds: float = Field(default=2, ge=0, le=10)
    circuit_failure_threshold: int = Field(default=3, ge=1, le=20)
    circuit_cooldown_seconds: float = Field(default=10, gt=0, le=300)
    telemetry_enabled: bool = False
    otlp_endpoint: str = "http://localhost:4318/v1/traces"
    telemetry_export_timeout: float = Field(default=2, gt=0, le=10)


@lru_cache
def get_settings() -> Settings:
    return Settings()
