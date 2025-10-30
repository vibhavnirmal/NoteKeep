from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "NoteKeep"
    database_url: str = f"sqlite:///{Path.cwd() / 'notekeep.db'}"
    telegram_bot_token: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
