import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    SUPABASE_DB_URL: str
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: str REPLACED_SECRET
    WEBHOOK_PATH: str = "/webhook"
    HOST: str = "0.0.0.0"
    PORT: int = 7860

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def resolve_webhook_url(self):
        if not self.WEBHOOK_URL:
            space_host = os.environ.get("SPACE_HOST")
            if space_host:
                self.WEBHOOK_URL = f"https://{space_host}"
        return self

settings = Settings()