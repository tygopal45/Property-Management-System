"""Settings. Everything that differs between machines is an environment variable."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Local default matches docker-compose.yml. Overridden in every other environment.
    database_url: str = "mysql+pymysql://rental:rental@127.0.0.1:3306/rental"

    jwt_secret: str = "dev-secret-not-for-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # schema.md 5.1: how long after the 1st before an unpaid month counts as overdue.
    grace_period_days: int = 5

    cookie_name: str = "session"
    cookie_secure: bool = False  # True in production, where everything is HTTPS
    cors_origins: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
