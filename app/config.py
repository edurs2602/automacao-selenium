from __future__ import annotations
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DOWNLOAD_DIR: Path = Path("data/dom")
    SELENIUM_REMOTE_URL: str | None = None
    CHROME_HEADLESS: bool = True

    DATABASE_URL: str = ""
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "minha_app"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    def model_post_init(self, __context: dict | None) -> None:
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )

settings = Settings()
settings.DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
