"""Shared ingestion path for connector API pulls -- normalizes RawUsageRecord
into UsageRecord rows exactly like csv_import_service does for CSV rows, then
runs them through the same costing_engine. This is what keeps API-pulled and
CSV-imported usage indistinguishable to the costing/allocation logic.
"""

from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.connectors.base import RawUsageRecord
from app.connectors.registry import get_connector
from app.models.provider import Provider
from app.models.usage_record import UsageRecord, UsageSourceType
from app.services.budget_engine import evaluate_all_active_budgets
from app.services.costing_engine import price_usage_records


class ConnectorNotFoundError(ValueError):
    pass


class ProviderNotFoundError(ValueError):
    pass


def ingest_raw_usage_records(
    db: Session, provider: Provider, raw_records: list[RawUsageRecord], source_reference: str
) -> list[UsageRecord]:
    usage_records = [
        UsageRecord(
            provider_id=provider.id,
            department_id=None,  # resolved later by allocation_service, same as CSV rows
            sku_code=r.sku_code,
            quantity=r.quantity,
            unit=r.unit,
            period_start=r.period_start,
            period_end=r.period_end,
            source_type=UsageSourceType.api_pull,
            source_reference=source_reference,
            raw_payload_ref=r.raw_payload_ref,
            api_key_label=r.api_key_label,
            tag_value=r.tag_value,
        )
        for r in raw_records
    ]
    db.add_all(usage_records)
    db.commit()
    for ur in usage_records:
        db.refresh(ur)
    return usage_records


def run_connector_pull(db: Session, provider_code: str, period_start: date, period_end: date) -> dict:
    provider = db.query(Provider).filter(Provider.code == provider_code).first()
    if provider is None:
        raise ProviderNotFoundError(f"Unknown provider_code: {provider_code}")

    connector = get_connector(provider_code)
    if connector is None:
        raise ConnectorNotFoundError(f"No API connector available for provider_code: {provider_code}")

    raw_records = connector.fetch_usage(period_start, period_end)  # raises ConnectorUnavailableError if not ready

    source_reference = f"api_pull:{provider_code}:{period_start}_{period_end}:{datetime.now(timezone.utc).isoformat()}"
    usage_records = ingest_raw_usage_records(db, provider, raw_records, source_reference)

    if not usage_records:
        return {
            "usage_records_created": 0,
            "cost_line_items_created": 0,
            "needs_pricing_rule_count": 0,
            "needs_allocation_count": 0,
        }

    line_items = price_usage_records(db, usage_records)
    evaluate_all_active_budgets(db)
    return {
        "usage_records_created": len(usage_records),
        "cost_line_items_created": len(line_items),
        "needs_pricing_rule_count": sum(1 for li in line_items if li.needs_pricing_rule),
        "needs_allocation_count": sum(1 for li in line_items if li.needs_allocation),
    }
