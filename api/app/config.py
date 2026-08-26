"""Application settings.

Every environment variable the service needs is declared here so that a missing or malformed
value fails loudly at startup rather than surfacing as a confusing ``None`` deep in a request.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://truckbuild:truckbuild@localhost:5433/truckbuild"
    )

    # Origins allowed to call this API from a browser. Locked down to the deployed web app in
    # production; localhost is only a development convenience.
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # Bearer token guarding the admin endpoints. Deliberately minimal for now -- see
    # docs/decisions.md; the upgrade path is real user accounts.
    admin_token: str = Field(default="dev-admin-token")

    # Shared secret for the Next.js cache revalidation webhook.
    revalidate_secret: str = Field(default="dev-revalidate-secret")
    web_base_url: str = Field(default="http://localhost:3000")

    # Outbound mail. Absent in development, in which case the mailer logs instead of sending.
    resend_api_key: str | None = Field(default=None)
    sales_inbox: str = Field(default="sales@example.com")

    environment: str = Field(default="development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
