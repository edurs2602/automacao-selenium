from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    DOWNLOAD_DIR: Path = Path("data/dom")
    SELENIUM_REMOTE_URL: str | None = None
    CHROME_HEADLESS: bool = True


settings = Settings()

settings.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
