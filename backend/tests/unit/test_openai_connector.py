from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx

from app.connectors.base import ConnectorUnavailableError
from app.connectors.openai_connector import OpenAIConnector


def test_capabilities_unavailable_without_admin_key():
    connector = OpenAIConnector(admin_api_key=None)
    caps = connector.capabilities()
    assert caps.supports_usage_pull is False
    assert "OPENAI_ADMIN_API_KEY" in caps.unavailable_reason


@respx.mock
def test_capabilities_gracefully_degrades_on_404():
    """This is the critical test: OpenAI's Costs API has had inconsistent
    rollout, returning 404 for some orgs even with a valid key. The connector
    must detect this and report itself unavailable rather than assume success."""
    respx.get("https://api.openai.com/v1/organization/costs").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    connector = OpenAIConnector(admin_api_key="sk-admin-xxx")
    caps = connector.capabilities()

    assert caps.supports_usage_pull is False
    assert "404" in caps.unavailable_reason
    assert "CSV" in caps.unavailable_reason


@respx.mock
def test_fetch_usage_raises_connector_unavailable_when_endpoint_404s():
    respx.get("https://api.openai.com/v1/organization/costs").mock(
        return_value=httpx.Response(404, json={"error": "not found"})
    )
    connector = OpenAIConnector(admin_api_key="sk-admin-xxx")

    with pytest.raises(ConnectorUnavailableError):
        connector.fetch_usage(date(2026, 1, 1), date(2026, 1, 31))


@respx.mock
def test_fetch_usage_parses_mocked_response_when_available():
    probe_and_data_response = {
        "data": [
            {
                "start_time": 1767225600,  # 2026-01-01
                "end_time": 1767312000,
                "results": [
                    {"line_item": "gpt-5-completions", "project_id": "proj-alpha", "amount": {"value": 12.50}}
                ],
            }
        ],
        "next_page": None,
    }
    respx.get("https://api.openai.com/v1/organization/costs").mock(
        return_value=httpx.Response(200, json=probe_and_data_response)
    )

    connector = OpenAIConnector(admin_api_key="sk-admin-xxx")
    assert connector.capabilities().supports_usage_pull is True

    records = connector.fetch_usage(date(2026, 1, 1), date(2026, 1, 1))
    assert len(records) == 1
    assert records[0].sku_code == "gpt-5-completions"
    assert records[0].tag_value == "proj-alpha"
    assert records[0].provider_reported_amount == Decimal("12.5")


@respx.mock
def test_test_connection_reflects_capabilities():
    respx.get("https://api.openai.com/v1/organization/costs").mock(return_value=httpx.Response(404))
    connector = OpenAIConnector(admin_api_key="sk-admin-xxx")
    status = connector.test_connection()
    assert status.ok is False
