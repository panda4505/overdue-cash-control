from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/occ"

    # LLM
    OPENAI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""

    # Email
    POSTMARK_SERVER_TOKEN: str = ""
    POSTMARK_INBOUND_WEBHOOK_SECRET: str = ""

    # Auth
    SECRET_KEY: str = "dev-secret-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week

    # Frontend
    FRONTEND_URL: str = "http://localhost:3000"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
