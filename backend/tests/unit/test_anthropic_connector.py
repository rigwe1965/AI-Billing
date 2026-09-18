from datetime import date
from decimal import Decimal

import httpx
import respx

from app.connectors.anthropic_connector import AnthropicConnector
from app.connectors.base import ConnectorUnavailableError
import pytest


def test_capabilities_unavailable_without_admin_key():
    connector = AnthropicConnector(admin_api_key=None)
    caps = connector.capabilities()
    assert caps.supports_usage_pull is False
    assert "ANTHROPIC_ADMIN_API_KEY" in caps.unavailable_reason


def test_capabilities_available_with_admin_key():
    connector = AnthropicConnector(admin_api_key="sk-ant-admin-xxx")
    caps = connector.capabilities()
    assert caps.supports_usage_pull is True
    assert caps.supports_cost_reconciliation is True


def test_fetch_usage_raises_when_unavailable():
    connector = AnthropicConnector(admin_api_key=None)
    with pytest.raises(ConnectorUnavailableError):
        connector.fetch_usage(date(2026, 1, 1), date(2026, 1, 31))


@respx.mock
def test_fetch_usage_parses_mocked_response_into_raw_records():
    mocked_response = {
        "data": [
            {
                "starting_at": "2026-01-05T00:00:00Z",
                "ending_at": "2026-01-06T00:00:00Z",
                "results": [
                    {
                        "model": "claude-sonnet-4-5",
                        "api_key_id": "key-eng",
                        "uncached_input_tokens": 2_000_000,
                        "output_tokens": 500_000,
                        "cache_creation": {
                            "ephemeral_5m_input_tokens": 0,
                            "ephemeral_1h_input_tokens": 0,
                        },
                        "cache_read_input_tokens": 100_000,
                    }
                ],
            }
        ],
        "has_more": False,
    }
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json=mocked_response)
    )

    connector = AnthropicConnector(admin_api_key="sk-ant-admin-xxx")
    records = connector.fetch_usage(date(2026, 1, 5), date(2026, 1, 6))

    by_sku = {r.sku_code: r for r in records}
    assert by_sku["claude-sonnet-4-5-input-tokens"].quantity == Decimal("2000000")
    assert by_sku["claude-sonnet-4-5-output-tokens"].quantity == Decimal("500000")
    assert by_sku["claude-sonnet-4-5-cache-read-tokens"].quantity == Decimal("100000")
    assert "claude-sonnet-4-5-cache-write-tokens" not in by_sku  # zero-valued field is skipped
    assert all(r.api_key_label == "key-eng" for r in by_sku.values())
    assert all(r.period_start == date(2026, 1, 5) for r in by_sku.values())


@respx.mock
def test_fetch_usage_sums_cache_creation_tiers_into_one_sku():
    mocked_response = {
        "data": [
            {
                "starting_at": "2026-01-05T00:00:00Z",
                "ending_at": "2026-01-06T00:00:00Z",
                "results": [
                    {
                        "model": "claude-sonnet-4-5",
                        "cache_creation": {
                            "ephemeral_5m_input_tokens": 30_000,
                            "ephemeral_1h_input_tokens": 70_000,
                        },
                    }
                ],
            }
        ],
        "has_more": False,
    }
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(200, json=mocked_response)
    )

    connector = AnthropicConnector(admin_api_key="sk-ant-admin-xxx")
    records = connector.fetch_usage(date(2026, 1, 5), date(2026, 1, 6))

    by_sku = {r.sku_code: r for r in records}
    assert by_sku["claude-sonnet-4-5-cache-write-tokens"].quantity == Decimal("100000")


@respx.mock
def test_fetch_usage_follows_pagination():
    page_1 = {
        "data": [
            {
                "starting_at": "2026-01-05T00:00:00Z",
                "results": [{"model": "claude-sonnet-4-5", "uncached_input_tokens": 1_000_000}],
            }
        ],
        "has_more": True,
        "next_page": "cursor-2",
    }
    page_2 = {
        "data": [
            {
                "starting_at": "2026-01-06T00:00:00Z",
                "results": [{"model": "claude-sonnet-4-5", "uncached_input_tokens": 2_000_000}],
            }
        ],
        "has_more": False,
    }

    route = respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages")
    route.side_effect = [httpx.Response(200, json=page_1), httpx.Response(200, json=page_2)]

    connector = AnthropicConnector(admin_api_key="sk-ant-admin-xxx")
    records = connector.fetch_usage(date(2026, 1, 5), date(2026, 1, 6))

    assert len(records) == 2
    assert sum(r.quantity for r in records) == Decimal("3000000")


@respx.mock
def test_test_connection_reports_http_error():
    respx.get("https://api.anthropic.com/v1/organizations/usage_report/messages").mock(
        return_value=httpx.Response(401, text="unauthorized")
    )
    connector = AnthropicConnector(admin_api_key="bad-key")
    status = connector.test_connection()
    assert status.ok is False
    assert "401" in status.detail
