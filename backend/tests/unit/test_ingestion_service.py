from datetime import date
from decimal import Decimal

import pytest

from app.connectors.base import ConnectorUnavailableError, RawUsageRecord
from app.models.pricing_rate import PricingRate
from app.models.usage_record import UsageSourceType
from app.services import ingestion_service


class FakeConnector:
    provider_code = "anthropic"

    def __init__(self, records, unavailable=False):
        self._records = records
        self._unavailable = unavailable

    def fetch_usage(self, period_start, period_end):
        if self._unavailable:
            raise ConnectorUnavailableError("no credentials")
        return self._records


def test_run_connector_pull_ingests_and_prices_like_csv(db_session, anthropic_provider, monkeypatch):
    db_session.add(
        PricingRate(
            provider_id=anthropic_provider.id,
            sku_code="claude-sonnet-input-tokens",
            unit="per_1m_tokens",
            rate_amount=Decimal("3.00"),
            effective_from=date(2026, 1, 1),
            source="manual_admin_entry",
        )
    )
    db_session.commit()

    fake = FakeConnector(
        records=[
            RawUsageRecord(
                sku_code="claude-sonnet-input-tokens",
                quantity=Decimal("2000000"),
                unit="tokens",
                period_start=date(2026, 1, 10),
                period_end=date(2026, 1, 10),
                api_key_label="key-eng",
            )
        ]
    )
    monkeypatch.setattr(ingestion_service, "get_connector", lambda code: fake)

    result = ingestion_service.run_connector_pull(db_session, "anthropic", date(2026, 1, 1), date(2026, 1, 31))

    assert result["usage_records_created"] == 1
    assert result["cost_line_items_created"] == 1
    assert result["needs_pricing_rule_count"] == 0

    usage_record = db_session.query(ingestion_service.UsageRecord).one()
    assert usage_record.source_type == UsageSourceType.api_pull
    assert usage_record.api_key_label == "key-eng"
    assert usage_record.source_reference.startswith("api_pull:anthropic:")


def test_run_connector_pull_propagates_unavailable_error(db_session, anthropic_provider, monkeypatch):
    fake = FakeConnector(records=[], unavailable=True)
    monkeypatch.setattr(ingestion_service, "get_connector", lambda code: fake)

    with pytest.raises(ConnectorUnavailableError):
        ingestion_service.run_connector_pull(db_session, "anthropic", date(2026, 1, 1), date(2026, 1, 31))


def test_run_connector_pull_unknown_provider_raises(db_session):
    with pytest.raises(ingestion_service.ProviderNotFoundError):
        ingestion_service.run_connector_pull(db_session, "nonexistent", date(2026, 1, 1), date(2026, 1, 31))
