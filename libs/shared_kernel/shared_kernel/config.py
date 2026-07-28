from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "unknown"
    env: str = "dev"
    log_level: str = "INFO"

    jwt_secret: str = "dev-secret-change-me-in-production"
    jwt_alg: str = "HS256"
    jwt_expire_minutes: int = 60

    database_url: str | None = None
    mongo_url: str | None = None
    mongo_db: str | None = None
    redis_url: str | None = None

    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    event_exchange: str = "platform.events"

    platform_account_id: str = "00000000-0000-0000-0000-000000000001"


settings = Settings()
