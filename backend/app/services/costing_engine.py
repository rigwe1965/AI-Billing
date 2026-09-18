"""Deterministic usage -> cost computation.

Hard rule: this module NEVER estimates a price or a department. If no active
pricing_rate matches a usage_record's provider/sku/date, the resulting
cost_line_item is persisted with computed_amount=None and needs_pricing_rule=True.
If no allocation (direct/key/tag/manual) resolves a department, the line item is
persisted with department_id=None and needs_allocation=True. Both failure modes
surface in the "needs attention" dashboard lists instead of guessing.

Unit conversion: pricing_rates store a `unit` such as "per_1k_tokens",
"per_1m_tokens", "per_token", "per_seat_month", "per_request". usage_records
store a `unit` for the raw quantity (currently always matching one of the same
per-item units, e.g. quantity is in raw tokens with unit="tokens"). The
conversion table below is the single place that knows how to reconcile them.
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.cost_line_item import CostLineItem, AllocationMethod
from app.models.pricing_rate import PricingRate
from app.models.usage_record import UsageRecord
from app.services.allocation_service import resolve_allocations

# Maps a pricing-rate unit to how many raw usage units it covers.
_RATE_UNIT_DIVISOR = {
    "per_token": Decimal("1"),
    "per_1k_tokens": Decimal("1000"),
    "per_1m_tokens": Decimal("1000000"),
    "per_request": Decimal("1"),
    "per_seat_month": Decimal("1"),
}


class UnsupportedUnitError(ValueError):
    pass


def find_active_pricing_rate(db: Session, provider_id: int, sku_code: str, on_date) -> PricingRate | None:
    return (
        db.query(PricingRate)
        .filter(
            PricingRate.provider_id == provider_id,
            PricingRate.sku_code == sku_code,
            PricingRate.effective_from <= on_date,
        )
        .filter((PricingRate.effective_to.is_(None)) | (PricingRate.effective_to >= on_date))
        .order_by(PricingRate.effective_from.desc())
        .first()
    )


def upsert_pricing_rate(
    db: Session,
    provider_id: int,
    sku_code: str,
    unit: str,
    rate_amount: Decimal,
    currency: str,
    effective_from: date,
    source: str,
    created_by_user_id: int | None = None,
) -> PricingRate:
    """Adds a new versioned rate for provider_id/sku_code, closing whatever
    row was previously open (effective_to IS NULL) the day before this one
    starts. Never overwrites a row in place -- shared by POST /api/pricing
    and load_pricing_configs.py so both go through the identical versioning
    rule.
    """
    existing = (
        db.query(PricingRate)
        .filter(
            PricingRate.provider_id == provider_id,
            PricingRate.sku_code == sku_code,
            PricingRate.effective_to.is_(None),
        )
        .first()
    )
    if existing:
        existing.effective_to = effective_from - timedelta(days=1)

    rate = PricingRate(
        provider_id=provider_id,
        sku_code=sku_code,
        unit=unit,
        rate_amount=rate_amount,
        currency=currency,
        effective_from=effective_from,
        effective_to=None,
        source=source,
        created_by_user_id=created_by_user_id,
    )
    db.add(rate)
    db.commit()
    db.refresh(rate)
    return rate


def compute_amount(quantity: Decimal, rate: PricingRate) -> Decimal:
    divisor = _RATE_UNIT_DIVISOR.get(rate.unit)
    if divisor is None:
        raise UnsupportedUnitError(f"Unknown pricing rate unit: {rate.unit!r}")
    return (Decimal(quantity) / divisor) * Decimal(rate.rate_amount)


def price_usage_record(db: Session, usage_record: UsageRecord) -> list[CostLineItem]:
    """Prices a single usage_record and returns unsaved CostLineItem(s) -- more
    than one when a manual allocation splits the cost across departments.
    """
    rate = find_active_pricing_rate(
        db, usage_record.provider_id, usage_record.sku_code, usage_record.period_start
    )
    allocations = resolve_allocations(db, usage_record)

    total_amount = None
    if rate is not None:
        total_amount = compute_amount(Decimal(usage_record.quantity), rate)

    if not allocations:
        return [
            CostLineItem(
                usage_record_id=usage_record.id,
                pricing_rate_id=rate.id if rate else None,
                department_id=None,
                computed_amount=total_amount,
                currency=rate.currency if rate else "USD",
                allocation_method=AllocationMethod.unallocated,
                needs_pricing_rule=rate is None,
                needs_allocation=True,
            )
        ]

    return [
        CostLineItem(
            usage_record_id=usage_record.id,
            pricing_rate_id=rate.id if rate else None,
            department_id=alloc.department_id,
            computed_amount=(total_amount * alloc.fraction) if total_amount is not None else None,
            currency=rate.currency if rate else "USD",
            allocation_method=alloc.method,
            allocation_reference_id=alloc.reference_id,
            needs_pricing_rule=rate is None,
            needs_allocation=False,
        )
        for alloc in allocations
    ]


def live_cost_line_items(db: Session):
    """Query for cost_line_items that reflect current state: excludes rows that
    have since been reversed, and excludes reversal rows themselves (they are
    bookkeeping corrections, not standalone facts to sum or flag). Reversal +
    fresh-priced rows together already net out to the correct total if you sum
    everything, but for "needs attention" lists and for a single clean summary
    query, only the live set should be considered.
    """
    reversed_ids = db.query(CostLineItem.reverses_line_item_id).filter(
        CostLineItem.reverses_line_item_id.isnot(None)
    )
    return db.query(CostLineItem).filter(
        CostLineItem.reverses_line_item_id.is_(None),
        ~CostLineItem.id.in_(reversed_ids),
    )


def _reverse_line_items(db: Session, usage_record_id: int) -> None:
    """Inserts reversal rows for every not-yet-reversed cost_line_item of a usage
    record. Never deletes or mutates the originals -- that's the audit trail."""
    existing = db.query(CostLineItem).filter(CostLineItem.usage_record_id == usage_record_id).all()
    already_reversed_ids = {li.reverses_line_item_id for li in existing if li.reverses_line_item_id}
    to_reverse = [li for li in existing if li.reverses_line_item_id is None and li.id not in already_reversed_ids]

    for li in to_reverse:
        db.add(
            CostLineItem(
                usage_record_id=li.usage_record_id,
                pricing_rate_id=li.pricing_rate_id,
                department_id=li.department_id,
                computed_amount=-li.computed_amount if li.computed_amount is not None else None,
                currency=li.currency,
                allocation_method=li.allocation_method,
                needs_pricing_rule=li.needs_pricing_rule,
                needs_allocation=li.needs_allocation,
                reverses_line_item_id=li.id,
            )
        )


def reprice_usage_record(db: Session, usage_record: UsageRecord) -> list[CostLineItem]:
    """Re-derives cost line items for a usage_record whose allocation or pricing
    inputs changed after it was first priced (e.g. a manual allocation was just
    added, or a new key/tag mapping now applies). Reverses the old line item(s)
    rather than mutating them, then prices fresh -- so the audit trail always
    shows both the original and the correction.
    """
    _reverse_line_items(db, usage_record.id)
    new_items = price_usage_record(db, usage_record)
    db.add_all(new_items)
    db.commit()
    for li in new_items:
        db.refresh(li)
    return new_items


def price_usage_records(db: Session, usage_records: list[UsageRecord]) -> list[CostLineItem]:
    """Prices a batch and persists the resulting cost_line_items.

    Idempotency: callers are responsible for not re-pricing a usage_record that
    already has a non-reversed cost_line_item; correcting a priced record means
    inserting a reversal row plus a new priced row, never mutating this one.
    """
    line_items = [li for ur in usage_records for li in price_usage_record(db, ur)]
    db.add_all(line_items)
    db.commit()
    for li in line_items:
        db.refresh(li)
    return line_items
