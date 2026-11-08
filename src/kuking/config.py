from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

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

settings = Settings()