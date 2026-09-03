"""Settings. Everything that differs between machines is an environment variable."""

from functools import lru_cache

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Local default matches docker-compose.yml. Overridden in every other environment.
    database_url: str = "postgresql+psycopg://rental:rental@127.0.0.1:5432/rental"

    # No default, deliberately. A default here is a foot-gun: the app would boot happily with a
    # secret that is public in the repository, and anyone could forge a session cookie for user 1
    # and be a manager without a password. That is not hypothetical — it was demonstrated against
    # this app while the default existed. One forgotten environment variable on deploy day is all
    # it took, and nothing warned. Now the app refuses to start instead.
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    # schema.md 5.1: how long after the 1st before an unpaid month counts as overdue.
    grace_period_days: int = 5

    cookie_name: str = "session"
    cookie_secure: bool = False  # True in production, where everything is HTTPS
    cors_origins: str = "http://localhost:5173"

    @field_validator("database_url")
    @classmethod
    def name_the_driver(cls, value: str) -> str:
        """Rewrite a bare Postgres URL to name psycopg 3 explicitly.

        This exists because the hosting platform generates the value and we cannot edit it.
        Render hands out `postgres://...`, and SQLAlchemy maps both that and a bare
        `postgresql://` to psycopg **2**, which is not installed — so the app would die at import
        with `ModuleNotFoundError: psycopg2` on a connection string that is perfectly correct.

        Rewriting it here rather than documenting "remember to add +psycopg" is the whole point: a
        deploy-time instruction that must be remembered is a deploy-time instruction that will be
        forgotten, and this one fails at startup rather than at the first query.
        """
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @field_validator("jwt_secret")
    @classmethod
    def refuse_a_weak_secret(cls, value: str) -> str:
        if value in REJECTED_SECRETS or len(value) < 32:
            raise ValueError(
                "JWT_SECRET must be a real random value of at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        return value

    @field_validator("cors_origins")
    @classmethod
    def refuse_a_wildcard_origin(cls, value: str) -> str:
        """`*` with credentials is worse than it looks.

        Starlette does not send a literal `*` when credentials are allowed — it reflects the
        caller's origin and sets `allow-credentials: true`, so *any* site could read authenticated
        responses. `SameSite=Lax` is what stops that today, and the moment the browser app and the
        API sit on different domains that cookie has to become `SameSite=None` and the protection
        goes. Refusing the wildcard here means that change cannot quietly open a hole later.
        """
        if "*" in value:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*': this API allows credentials, and a wildcard "
                "origin would let any site read authenticated responses. List the exact origins."
            )
        return value


# Values that must never be accepted, whatever the environment.
REJECTED_SECRETS = {
    "dev-secret-not-for-production",
    "change-me",
    "secret",
    "changeme",
}


@lru_cache
def get_settings() -> Settings:
    """Reads the environment once. Raises at import if the configuration is unsafe, which is the
    intended behaviour — a misconfigured deployment should fail loudly, not serve traffic."""
    try:
        return Settings()
    except ValidationError as exc:
        raise SystemExit(f"Refusing to start — bad configuration:\n{exc}") from exc


settings = get_settings()
