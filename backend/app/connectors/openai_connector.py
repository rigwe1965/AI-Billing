"""OpenAI organization usage/costs connector.

An org-level Costs/Usage API exists (`/v1/organization/costs`,
`/v1/organization/usage/completions`) but community reports show inconsistent
availability across organizations (some see 404s). Unlike the Anthropic
connector, this one actively probes the endpoint in capabilities() rather than
assuming it works just because a key is configured -- callers MUST check
capabilities().supports_usage_pull and fall back to CSV import when False.

ChatGPT Enterprise seat costs have no public consumption API as of the last
research pass -- seats are always CSV/manual entry, never pulled here.

Exact endpoint paths/response shape MUST be re-verified against
https://platform.openai.com/docs/api-reference before relying on this in
production.
"""

from datetime import date
from decimal import Decimal

import httpx

from app.connectors.base import (
    AbstractProviderConnector,
    ConnectionStatus,
    ConnectorCapabilities,
    ConnectorUnavailableError,
    RawUsageRecord,
)

API_BASE_URL = "https://api.openai.com"


class OpenAIConnector(AbstractProviderConnector):
    provider_code = "openai"

    def __init__(self, admin_api_key: str | None, org_id: str | None = None, client: httpx.Client | None = None):
        self._admin_api_key = admin_api_key
        self._org_id = org_id
        self._client = client or httpx.Client(base_url=API_BASE_URL, timeout=30.0)

    def _headers(self) -> dict:
        headers = {"Authorization": f"Bearer {self._admin_api_key or ''}"}
        if self._org_id:
            headers["OpenAI-Organization"] = self._org_id
        return headers

    def capabilities(self) -> ConnectorCapabilities:
        if not self._admin_api_key:
            return ConnectorCapabilities(
                supports_usage_pull=False,
                supports_cost_reconciliation=False,
                unavailable_reason="OPENAI_ADMIN_API_KEY not configured",
            )

        try:
            resp = self._client.get(
                "/v1/organization/costs", headers=self._headers(), params={"limit": 1}
            )
        except httpx.HTTPError as exc:
            return ConnectorCapabilities(
                supports_usage_pull=False,
                supports_cost_reconciliation=False,
                unavailable_reason=f"Probe request failed: {exc}",
            )

        if resp.status_code == 200:
            return ConnectorCapabilities(supports_usage_pull=True, supports_cost_reconciliation=True)
        if resp.status_code == 404:
            return ConnectorCapabilities(
                supports_usage_pull=False,
                supports_cost_reconciliation=False,
                unavailable_reason=(
                    "Costs API returned 404 for this organization -- known to be "
                    "inconsistently rolled out; use CSV import for OpenAI usage instead"
                ),
            )
        return ConnectorCapabilities(
            supports_usage_pull=False,
            supports_cost_reconciliation=False,
            unavailable_reason=f"Unexpected HTTP {resp.status_code} probing Costs API",
        )

    def test_connection(self) -> ConnectionStatus:
        caps = self.capabilities()
        if not caps.supports_usage_pull:
            return ConnectionStatus(ok=False, detail=caps.unavailable_reason or "Unavailable")
        return ConnectionStatus(ok=True, detail="Connected")

    def fetch_usage(self, period_start: date, period_end: date) -> list[RawUsageRecord]:
        caps = self.capabilities()
        if not caps.supports_usage_pull:
            raise ConnectorUnavailableError(caps.unavailable_reason)

        records: list[RawUsageRecord] = []
        page_cursor: str | None = None

        while True:
            params = {
                "start_time": _unix(period_start),
                "end_time": _unix(period_end),
                "group_by": ["line_item", "project_id"],
            }
            if page_cursor:
                params["page"] = page_cursor

            resp = self._client.get("/v1/organization/costs", headers=self._headers(), params=params)
            resp.raise_for_status()
            payload = resp.json()

            for bucket in payload.get("data", []):
                records.extend(_parse_cost_bucket(bucket))

            page_cursor = payload.get("next_page")
            if not page_cursor:
                break

        return records


def _unix(d: date) -> int:
    from datetime import datetime, timezone

    return int(datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc).timestamp())


def _parse_cost_bucket(bucket: dict) -> list[RawUsageRecord]:
    period_start = date.fromtimestamp(bucket["start_time"])
    period_end = date.fromtimestamp(bucket.get("end_time", bucket["start_time"]))

    out: list[RawUsageRecord] = []
    for result in bucket.get("results", []):
        line_item = result.get("line_item", "unknown-line-item")
        project_id = result.get("project_id")
        amount = result.get("amount", {}).get("value")

        out.append(
            RawUsageRecord(
                sku_code=line_item,
                # OpenAI's cost endpoint reports $ directly rather than raw token
                # counts, so quantity here is treated as pre-priced -- pricing_rates
                # for OpenAI SKUs sourced this way should use unit="per_request"
                # with rate_amount=1 (a pass-through), OR usage should instead be
                # pulled from a token-level usage endpoint when available. Flagged
                # for revisiting once the real response shape is confirmed.
                quantity=Decimal(str(amount)) if amount is not None else Decimal("0"),
                unit="per_request",
                period_start=period_start,
                period_end=period_end,
                tag_value=project_id,
                provider_reported_amount=Decimal(str(amount)) if amount is not None else None,
            )
        )
    return out
