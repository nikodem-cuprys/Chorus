"""Settings read from the environment (CHORUS_*), with defaults for a local run."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHORUS_")

    database_url: str = "postgresql+psycopg://chorus:chorus@localhost:5432/chorus"
    redis_url: str = "redis://localhost:6379/0"

    data_dir: Path = Path("/data")
    models_dir: Path = Path("/models")
    exports_dir: Path = Path("/exports")

    # The built frontend; served by the backend when the folder exists.
    frontend_dist: Path = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

    # Enables /api/dev, used to start dummy jobs while there are no real ones.
    dev: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
