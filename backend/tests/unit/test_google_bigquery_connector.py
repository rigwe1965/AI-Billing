from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from app.connectors.base import ConnectorUnavailableError
from app.connectors.google_bigquery_connector import GoogleBigQueryConnector, build_usage_query


@dataclass
class FakeRow:
    sku_description: str
    project_id: str
    usage_amount: float
    usage_unit: str
    reported_cost: float
    usage_date: date


class FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeBigQueryClient:
    def __init__(self, rows=None, raise_on_query=None):
        self._rows = rows or []
        self._raise_on_query = raise_on_query
        self.last_query = None

    def query(self, sql, job_config=None):
        self.last_query = sql
        if self._raise_on_query:
            raise self._raise_on_query
        return FakeQueryJob(self._rows)


def test_capabilities_unavailable_without_project_or_dataset():
    connector = GoogleBigQueryConnector(project=None, dataset=None)
    caps = connector.capabilities()
    assert caps.supports_usage_pull is False
    assert caps.requires_prerequisite == "Cloud Billing Detailed Data Export to BigQuery enabled"


def test_capabilities_available_when_configured():
    connector = GoogleBigQueryConnector(project="my-project", dataset="billing_export", client=FakeBigQueryClient())
    caps = connector.capabilities()
    assert caps.supports_usage_pull is True


def test_fetch_usage_raises_when_unavailable():
    connector = GoogleBigQueryConnector(project=None, dataset=None)
    with pytest.raises(ConnectorUnavailableError):
        connector.fetch_usage(date(2026, 1, 1), date(2026, 1, 31))


def test_build_usage_query_contains_dataset_table_and_date_range():
    query = build_usage_query("my-project", "billing_export", date(2026, 1, 1), date(2026, 1, 31))
    assert "`my-project.billing_export.gcp_billing_export_resource_v1_*`" in query
    assert "2026-01-01" in query
    assert "2026-01-31" in query
    assert "Vertex AI" in query


def test_fetch_usage_parses_rows_from_fake_client():
    rows = [
        FakeRow(
            sku_description="Vertex AI Gemini 2.5 Pro Input Tokens",
            project_id="proj-marketing",
            usage_amount=1_500_000,
            usage_unit="tokens",
            reported_cost=4.5,
            usage_date=date(2026, 1, 10),
        )
    ]
    connector = GoogleBigQueryConnector(
        project="my-project", dataset="billing_export", client=FakeBigQueryClient(rows=rows)
    )

    records = connector.fetch_usage(date(2026, 1, 1), date(2026, 1, 31))

    assert len(records) == 1
    r = records[0]
    assert r.sku_code == "Vertex AI Gemini 2.5 Pro Input Tokens"
    assert r.quantity == Decimal("1500000")
    assert r.tag_value == "proj-marketing"
    assert r.provider_reported_amount == Decimal("4.5")
    assert r.period_start == date(2026, 1, 10)


def test_test_connection_surfaces_query_failure():
    connector = GoogleBigQueryConnector(
        project="my-project",
        dataset="billing_export",
        client=FakeBigQueryClient(raise_on_query=RuntimeError("permission denied")),
    )
    status = connector.test_connection()
    assert status.ok is False
    assert "permission denied" in status.detail
