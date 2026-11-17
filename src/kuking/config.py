import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

class Settings(BaseSettings):
    GEMINI_API_KEY: str
    SUPABASE_DB_URL: str
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    WEBHOOK_URL: Optional[str] = None
    WEBHOOK_SECRET: str 
    WEBHOOK_PATH: str = "/webhook"
    HOST: str = "0.0.0.0"
    PORT: int = 7860

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def resolve_webhook_url(self):
        if not self.WEBHOOK_URL:
            space_host = os.environ.get("SPACE_HOST") # hf space
            if space_host:
                self.WEBHOOK_URL = f"https://{space_host}"

            railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN") # railway 
            if railway_domain:
                self.WEBHOOK_URL = f"https://{railway_domain}"
        return self

settings = Settings()