from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_SECRET_KEY: str = "change_me"
    LOG_LEVEL: str = "INFO"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    ALLOWED_HOSTS: List[str] = ["localhost", "sanjeevani.yourdomain.com"]

    # Twilio
    TWILIO_ACCOUNT_SID: str
    TWILIO_AUTH_TOKEN: str
    TWILIO_WHATSAPP_FROM: str = "whatsapp:+14155238886"
    TWILIO_SMS_FROM: str
    TWILIO_WEBHOOK_SECRET: str = ""

    # LLM
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str
    LLM_MODEL: str = "llama3-70b-8192"
    LLM_MAX_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.1
    LLM_TIMEOUT: float = 8.0  # seconds

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384

    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "sanjeevani_medical"
    RAG_TOP_K: int = 5

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"
    SESSION_TTL_SECONDS: int = 3600

    # Quality
    MAX_CONTEXT_TURNS: int = 5
    CONFIDENCE_THRESHOLD: float = 0.72

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    SENTRY_DSN: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
