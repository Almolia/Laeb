from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "wallet"
    database_url: str = "postgresql+psycopg://wallet:wallet@localhost:5432/wallet"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/%2F"
    event_exchange: str = "platform.events"
    platform_account_id: str = "00000000-0000-0000-0000-000000000001"
    mock_psp_url: str = "http://localhost:8020"
    wallet_callback_url: str = (
        "http://localhost:8005/api/v1/wallet/topups/callback"
    )
    log_level: str = "INFO"
    outbox_poll_seconds: float = Field(default=1.0, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
