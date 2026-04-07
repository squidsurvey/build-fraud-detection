from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://fraud_user:fraud_secret@localhost:5432/frauddb"
    REDIS_URL: str = "redis://:redis_secret@localhost:6379/0"
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/fraud-alert"
    SECRET_KEY: str = "changeme_in_production_32chars!!"
    API_DEBUG: bool = False

    # Fraud thresholds
    FRAUD_SCORE_HIGH: float = 0.75       # block transaction
    FRAUD_SCORE_MEDIUM: float = 0.50     # flag for review
    VELOCITY_MAX_TRANSACTIONS: int = 10  # per window
    VELOCITY_WINDOW_SECONDS: int = 3600  # 1 hour


settings = Settings()
