from app.connectors.anthropic_connector import AnthropicConnector
from app.connectors.base import AbstractProviderConnector
from app.connectors.google_bigquery_connector import GoogleBigQueryConnector
from app.connectors.openai_connector import OpenAIConnector
from app.core.config import settings


def get_connector(provider_code: str) -> AbstractProviderConnector | None:
    """Returns a fresh connector instance for the given provider code, wired up
    with whatever credentials are configured (may be None -- caller must check
    capabilities() before calling fetch_usage()). Returns None for provider
    codes that have no connector (e.g. "custom" -- CSV/manual only, always)."""
    if provider_code == "anthropic":
        return AnthropicConnector(admin_api_key=settings.anthropic_admin_api_key)
    if provider_code == "openai":
        return OpenAIConnector(admin_api_key=settings.openai_admin_api_key, org_id=settings.openai_org_id)
    if provider_code == "google":
        return GoogleBigQueryConnector(
            project=settings.google_bigquery_project, dataset=settings.google_bigquery_billing_dataset
        )
    return None
