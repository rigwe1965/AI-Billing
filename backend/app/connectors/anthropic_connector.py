"""Anthropic Admin API connector.

Uses the Usage & Cost Admin API (`/v1/organizations/usage_report/messages` and
`/v1/organizations/cost_report`), which requires a separate Admin API key
(`sk-ant-admin...`), not a regular API key. See docs/provider-connector-notes.md.

Field names in `_parse_usage_bucket` were verified on 2026-09-18 against the
live schema at
https://platform.claude.com/docs/en/api/beta/organization/usage_report/retrieve_messages
(not just the narrative usage-cost-api guide). All field access is
centralized there so a future schema drift only needs fixing in one place.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import httpx

from app.connectors.base import (
    AbstractProviderConnector,
    ConnectionStatus,
    ConnectorCapabilities,
    ConnectorUnavailableError,
    RawUsageRecord,
)

API_BASE_URL = "https://api.anthropic.com"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicConnector(AbstractProviderConnector):
    provider_code = "anthropic"

    def __init__(self, admin_api_key: str | None, client: httpx.Client | None = None):
        self._admin_api_key = admin_api_key
        self._client = client or httpx.Client(base_url=API_BASE_URL, timeout=30.0)

    def capabilities(self) -> ConnectorCapabilities:
        if not self._admin_api_key:
            return ConnectorCapabilities(
                supports_usage_pull=False,
                supports_cost_reconciliation=False,
                unavailable_reason="ANTHROPIC_ADMIN_API_KEY not configured",
            )
        return ConnectorCapabilities(supports_usage_pull=True, supports_cost_reconciliation=True)

    def _headers(self) -> dict:
        return {
            "x-api-key": self._admin_api_key or "",
            "anthropic-version": ANTHROPIC_VERSION,
        }

    def test_connection(self) -> ConnectionStatus:
        if not self._admin_api_key:
            return ConnectionStatus(ok=False, detail="No admin API key configured")
        try:
            resp = self._client.get(
                "/v1/organizations/usage_report/messages",
                headers=self._headers(),
                params={"starting_at": _iso(date.today() - timedelta(days=1)), "limit": 1},
            )
        except httpx.HTTPError as exc:
            return ConnectionStatus(ok=False, detail=f"Request failed: {exc}")
        if resp.status_code == 200:
            return ConnectionStatus(ok=True, detail="Connected")
        return ConnectionStatus(ok=False, detail=f"HTTP {resp.status_code}: {resp.text[:200]}")

    def fetch_usage(self, period_start: date, period_end: date) -> list[RawUsageRecord]:
        if not self.capabilities().supports_usage_pull:
            raise ConnectorUnavailableError(self.capabilities().unavailable_reason)

        records: list[RawUsageRecord] = []
        page_token: str | None = None

        while True:
            params: dict[str, Any] = {
                "starting_at": _iso(period_start),
                "ending_at": _iso(period_end),
                "group_by[]": ["model", "api_key_id"],
                "bucket_width": "1d",
            }
            if page_token:
                params["page"] = page_token

            resp = self._client.get(
                "/v1/organizations/usage_report/messages", headers=self._headers(), params=params
            )
            resp.raise_for_status()
            payload = resp.json()

            for bucket in payload.get("data", []):
                records.extend(_parse_usage_bucket(bucket))

            if not payload.get("has_more"):
                break
            page_token = payload.get("next_page")
            if not page_token:
                break

        return records


def _iso(d: date) -> str:
    return d.isoformat()


def _parse_usage_bucket(bucket: dict) -> list[RawUsageRecord]:
    """A bucket is one time-window's results, each result broken down by the
    requested group_by dimensions (model, api_key_id). Token counts come back
    per-type (input/output/cache) -- each becomes its own RawUsageRecord with a
    distinct sku_code so pricing_rates can price input vs. output separately.

    Real field names (confirmed against the live API schema): input tokens
    that weren't served from cache are `uncached_input_tokens`, not
    `input_tokens`; cache-write tokens are nested under `cache_creation` as
    `ephemeral_5m_input_tokens` and `ephemeral_1h_input_tokens`, not a flat
    `cache_creation_input_tokens`.
    """
    period_start = date.fromisoformat(bucket["starting_at"][:10])
    period_end = date.fromisoformat(bucket.get("ending_at", bucket["starting_at"])[:10])

    out: list[RawUsageRecord] = []
    for result in bucket.get("results", []):
        model = result.get("model") or "unknown-model"
        api_key_label = result.get("api_key_id")

        token_fields = {
            "uncached_input_tokens": f"{model}-input-tokens",
            "output_tokens": f"{model}-output-tokens",
            "cache_read_input_tokens": f"{model}-cache-read-tokens",
        }
        for field, sku_code in token_fields.items():
            quantity = result.get(field)
            if not quantity:
                continue
            out.append(
                RawUsageRecord(
                    sku_code=sku_code,
                    quantity=Decimal(str(quantity)),
                    unit="tokens",
                    period_start=period_start,
                    period_end=period_end,
                    api_key_label=api_key_label,
                )
            )

        cache_creation = result.get("cache_creation") or {}
        cache_write_tokens = Decimal(str(cache_creation.get("ephemeral_5m_input_tokens", 0))) + Decimal(
            str(cache_creation.get("ephemeral_1h_input_tokens", 0))
        )
        if cache_write_tokens:
            out.append(
                RawUsageRecord(
                    sku_code=f"{model}-cache-write-tokens",
                    quantity=cache_write_tokens,
                    unit="tokens",
                    period_start=period_start,
                    period_end=period_end,
                    api_key_label=api_key_label,
                )
            )
    return out
