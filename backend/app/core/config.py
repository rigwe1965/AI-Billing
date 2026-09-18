from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Spend Management"
    database_url: str = "sqlite:///./ai_billing.db"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 12

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


settings = Settings()
