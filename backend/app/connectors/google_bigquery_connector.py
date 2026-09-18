"""Google Gemini/Vertex AI connector -- queries the company's Cloud Billing
Detailed Data Export in BigQuery. There is no simple REST "usage cost" endpoint
for Gemini/Vertex the way Anthropic/OpenAI have one; this is the documented,
supported path (see docs/provider-connector-notes.md). Requires the company to
already have Cloud Billing export to BigQuery enabled -- that's an environment
prerequisite this connector does not set up itself.

Exact dataset/table naming (`gcp_billing_export_resource_v1_*`) and column
schema MUST be re-verified against
https://docs.cloud.google.com/billing/docs/how-to/export-data-bigquery-tables/detailed-usage
before relying on this in production.

The BigQuery client is dependency-injected so this connector is unit-testable
without a real GCP project -- `_get_client()` only imports/constructs the real
`google.cloud.bigquery.Client` when no client was injected and real use is needed.
"""

from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from app.connectors.base import (
    AbstractProviderConnector,
    ConnectionStatus,
    ConnectorCapabilities,
    ConnectorUnavailableError,
    RawUsageRecord,
)

_PREREQUISITE = "Cloud Billing Detailed Data Export to BigQuery enabled"


class BigQueryClientProtocol(Protocol):
    def query(self, sql: str, job_config: Any = None) -> Any:
        ...


def build_usage_query(project: str, dataset: str, period_start: date, period_end: date) -> str:
    """Builds the query as a plain string (with literal dates) rather than
    query parameters, since the exact QueryJobConfig parameter API varies by
    client library version and this keeps the connector easy to unit test by
    asserting on the SQL text."""
    return f"""
        SELECT
          sku.description AS sku_description,
          project.id AS project_id,
          usage.amount AS usage_amount,
          usage.unit AS usage_unit,
          cost AS reported_cost,
          DATE(usage_start_time) AS usage_date
        FROM `{project}.{dataset}.gcp_billing_export_resource_v1_*`
        WHERE service.description IN ('Vertex AI', 'Generative Language API')
          AND DATE(usage_start_time) BETWEEN DATE('{period_start.isoformat()}') AND DATE('{period_end.isoformat()}')
    """.strip()


class GoogleBigQueryConnector(AbstractProviderConnector):
    provider_code = "google"

    def __init__(
        self,
        project: str | None,
        dataset: str | None,
        client: BigQueryClientProtocol | None = None,
    ):
        self._project = project
        self._dataset = dataset
        self._client = client

    def capabilities(self) -> ConnectorCapabilities:
        if not self._project or not self._dataset:
            return ConnectorCapabilities(
                supports_usage_pull=False,
                supports_cost_reconciliation=True,
                requires_prerequisite=_PREREQUISITE,
                unavailable_reason="GOOGLE_BIGQUERY_PROJECT / GOOGLE_BIGQUERY_BILLING_DATASET not configured",
            )
        return ConnectorCapabilities(
            supports_usage_pull=True, supports_cost_reconciliation=True, requires_prerequisite=_PREREQUISITE
        )

    def _get_client(self) -> BigQueryClientProtocol:
        if self._client is not None:
            return self._client
        from google.cloud import bigquery  # lazy import -- only needed for real use

        self._client = bigquery.Client(project=self._project)
        return self._client

    def test_connection(self) -> ConnectionStatus:
        caps = self.capabilities()
        if not caps.supports_usage_pull:
            return ConnectionStatus(ok=False, detail=caps.unavailable_reason or "Unavailable")
        try:
            self._get_client().query("SELECT 1").result()
        except Exception as exc:  # noqa: BLE001 -- surfacing any client/query failure as a status
            return ConnectionStatus(ok=False, detail=f"BigQuery query failed: {exc}")
        return ConnectionStatus(ok=True, detail="Connected")

    def fetch_usage(self, period_start: date, period_end: date) -> list[RawUsageRecord]:
        caps = self.capabilities()
        if not caps.supports_usage_pull:
            raise ConnectorUnavailableError(caps.unavailable_reason)

        query = build_usage_query(self._project, self._dataset, period_start, period_end)
        rows = self._get_client().query(query).result()
        return [_parse_row(row) for row in rows]


def _parse_row(row: Any) -> RawUsageRecord:
    usage_date = row.usage_date if isinstance(row.usage_date, date) else date.fromisoformat(str(row.usage_date))
    return RawUsageRecord(
        sku_code=row.sku_description,
        quantity=Decimal(str(row.usage_amount)),
        unit=row.usage_unit,
        period_start=usage_date,
        period_end=usage_date,
        tag_value=row.project_id,
        provider_reported_amount=Decimal(str(row.reported_cost)) if row.reported_cost is not None else None,
    )
