from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


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


@lru_cache
def get_settings() -> Settings:
    return Settings()
