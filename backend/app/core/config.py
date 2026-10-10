import logging
import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Spend Management"
    database_url: str = "sqlite:///./ai_billing.db"
    # JWT signing key. Set SECRET_KEY (32+ chars) in backend/.env for any real
    # deployment. If it is unset or too short, a random per-process key is
    # generated instead: sessions then end on restart, but a publicly known
    # default can never be used to forge an admin token.
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 12
    # Set COOKIE_SECURE=true when serving over HTTPS so the session cookie is
    # never sent over plain HTTP. Left off by default for local http:// dev.
    cookie_secure: bool = False
    # Set ENABLE_DOCS=false in production to hide /docs, /redoc and /openapi.json.
    enable_docs: bool = True

    # Provider connector credentials -- all optional; a connector whose
    # credentials are unset reports itself unavailable via capabilities()
    # rather than failing at import/use time.
    anthropic_admin_api_key: str | None = None
    # Separate from anthropic_admin_api_key above: a normal Messages API key,
    # used only by insights_service.ask() to answer natural-language
    # questions about already-computed spend data -- never for billing pulls.
    anthropic_api_key: str | None = None
    openai_admin_api_key: str | None = None
    openai_org_id: str | None = None
    google_bigquery_project: str | None = None
    google_bigquery_billing_dataset: str | None = None
    google_application_credentials: str | None = None  # path to service account JSON

    @field_validator("secret_key")
    @classmethod
    def _require_strong_secret_key(cls, v: str) -> str:
        if len(v) < 32 or v == "dev-only-change-me":
            logging.getLogger(__name__).warning(
                "SECRET_KEY is unset or weak; using a random ephemeral key (sessions reset on restart)."
            )
            return secrets.token_urlsafe(48)
        return v


settings = Settings()
