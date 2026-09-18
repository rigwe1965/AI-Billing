from datetime import date
from decimal import Decimal

import pytest

from app.models.allocation_map import ManualAllocation
from app.models.cost_line_item import CostLineItem
from app.models.department import Department
from app.models.pricing_rate import PricingRate
from app.models.usage_record import UsageRecord, UsageSourceType
from app.services.costing_engine import (
    UnsupportedUnitError,
    compute_amount,
    find_active_pricing_rate,
    live_cost_line_items,
    price_usage_record,
    price_usage_records,
    reprice_usage_record,
)


def make_usage_record(provider_id, department_id, sku_code, quantity, unit, period_start, period_end=None):
    return UsageRecord(
        provider_id=provider_id,
        department_id=department_id,
        sku_code=sku_code,
        quantity=Decimal(quantity),
        unit=unit,
        period_start=period_start,
        period_end=period_end or period_start,
        source_type=UsageSourceType.csv_import,
        source_reference="test",
    )


def test_exact_known_cost_per_1m_tokens(db_session, anthropic_provider, engineering_dept):
    # 1,000,000 input tokens at $3.00 / 1M tokens => exactly $3.00
    rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="claude-sonnet-input-tokens",
        unit="per_1m_tokens",
        rate_amount=Decimal("3.00"),
        currency="USD",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        source="manual_admin_entry",
    )
    db_session.add(rate)
    db_session.commit()

    usage = make_usage_record(
        anthropic_provider.id,
        engineering_dept.id,
        "claude-sonnet-input-tokens",
        1_000_000,
        "tokens",
        date(2026, 1, 15),
    )
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    line_items = price_usage_record(db_session, usage)

    assert len(line_items) == 1
    line_item = line_items[0]
    assert line_item.needs_pricing_rule is False
    assert line_item.computed_amount == Decimal("3.00")
    assert line_item.pricing_rate_id == rate.id
    assert line_item.department_id == engineering_dept.id


def test_missing_rate_flags_needs_pricing_rule_never_guesses(db_session, anthropic_provider, engineering_dept):
    usage = make_usage_record(
        anthropic_provider.id,
        engineering_dept.id,
        "unknown-sku",
        500,
        "tokens",
        date(2026, 1, 15),
    )
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    line_items = price_usage_record(db_session, usage)

    assert len(line_items) == 1
    line_item = line_items[0]
    assert line_item.needs_pricing_rule is True
    assert line_item.needs_allocation is False  # department was already known
    assert line_item.computed_amount is None
    assert line_item.pricing_rate_id is None


def test_rate_change_boundary_uses_rate_active_on_usage_period_start(db_session, anthropic_provider, engineering_dept):
    old_rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="claude-sonnet-input-tokens",
        unit="per_1m_tokens",
        rate_amount=Decimal("3.00"),
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 1, 31),
        source="manual_admin_entry",
    )
    new_rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="claude-sonnet-input-tokens",
        unit="per_1m_tokens",
        rate_amount=Decimal("2.50"),
        effective_from=date(2026, 2, 1),
        effective_to=None,
        source="manual_admin_entry",
    )
    db_session.add_all([old_rate, new_rate])
    db_session.commit()

    usage_in_january = make_usage_record(
        anthropic_provider.id, engineering_dept.id, "claude-sonnet-input-tokens", 1_000_000, "tokens", date(2026, 1, 20)
    )
    usage_in_february = make_usage_record(
        anthropic_provider.id, engineering_dept.id, "claude-sonnet-input-tokens", 1_000_000, "tokens", date(2026, 2, 5)
    )
    db_session.add_all([usage_in_january, usage_in_february])
    db_session.commit()
    db_session.refresh(usage_in_january)
    db_session.refresh(usage_in_february)

    jan_item = price_usage_record(db_session, usage_in_january)[0]
    feb_item = price_usage_record(db_session, usage_in_february)[0]

    assert jan_item.computed_amount == Decimal("3.00")
    assert jan_item.pricing_rate_id == old_rate.id
    assert feb_item.computed_amount == Decimal("2.50")
    assert feb_item.pricing_rate_id == new_rate.id


def test_find_active_pricing_rate_ignores_expired_and_future_rates(db_session, anthropic_provider):
    expired = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="sku-a",
        unit="per_token",
        rate_amount=Decimal("1.0"),
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
        source="manual_admin_entry",
    )
    future = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="sku-a",
        unit="per_token",
        rate_amount=Decimal("2.0"),
        effective_from=date(2027, 1, 1),
        effective_to=None,
        source="manual_admin_entry",
    )
    db_session.add_all([expired, future])
    db_session.commit()

    result = find_active_pricing_rate(db_session, anthropic_provider.id, "sku-a", date(2026, 6, 1))

    assert result is None


@pytest.mark.parametrize(
    "unit,quantity,rate_amount,expected",
    [
        ("per_token", "100", "0.01", Decimal("1.00")),
        ("per_1k_tokens", "5000", "2.00", Decimal("10.00")),
        ("per_1m_tokens", "2500000", "4.00", Decimal("10.00")),
        ("per_seat_month", "3", "30.00", Decimal("90.00")),
        ("per_request", "50", "0.02", Decimal("1.00")),
    ],
)
def test_unit_conversion_table(unit, quantity, rate_amount, expected):
    rate = PricingRate(
        provider_id=1,
        sku_code="x",
        unit=unit,
        rate_amount=Decimal(rate_amount),
        effective_from=date(2026, 1, 1),
        source="test",
    )
    assert compute_amount(Decimal(quantity), rate) == expected


def test_unsupported_unit_raises_instead_of_guessing():
    rate = PricingRate(
        provider_id=1,
        sku_code="x",
        unit="per_fortnight",  # not a real unit in the conversion table
        rate_amount=Decimal("1.00"),
        effective_from=date(2026, 1, 1),
        source="test",
    )
    with pytest.raises(UnsupportedUnitError):
        compute_amount(Decimal("10"), rate)


def test_usage_with_no_department_is_flagged_unallocated_not_defaulted(db_session, anthropic_provider):
    rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="sku-b",
        unit="per_token",
        rate_amount=Decimal("1.00"),
        effective_from=date(2026, 1, 1),
        source="manual_admin_entry",
    )
    db_session.add(rate)
    db_session.commit()

    usage = make_usage_record(anthropic_provider.id, None, "sku-b", 10, "tokens", date(2026, 1, 10))
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    line_items = price_usage_record(db_session, usage)

    assert len(line_items) == 1
    line_item = line_items[0]
    assert line_item.department_id is None
    assert line_item.allocation_method.value == "unallocated"
    assert line_item.needs_allocation is True
    # Cost is still computed even though allocation is unresolved -- pricing and
    # allocation are independent concerns; only allocation is left for a human.
    assert line_item.computed_amount == Decimal("10.00")


def test_reprice_after_manual_allocation_reverses_old_line_and_lives_clean(
    db_session, anthropic_provider, engineering_dept
):
    marketing = Department(name="Marketing", code="MKT")
    db_session.add(marketing)
    db_session.commit()

    rate = PricingRate(
        provider_id=anthropic_provider.id,
        sku_code="sku-c",
        unit="per_token",
        rate_amount=Decimal("1.00"),
        effective_from=date(2026, 1, 1),
        source="manual_admin_entry",
    )
    db_session.add(rate)
    db_session.commit()

    usage = make_usage_record(anthropic_provider.id, None, "sku-c", 10, "tokens", date(2026, 1, 10))
    db_session.add(usage)
    db_session.commit()
    db_session.refresh(usage)

    initial_items = price_usage_records(db_session, [usage])
    assert len(initial_items) == 1
    assert initial_items[0].needs_allocation is True

    db_session.add_all(
        [
            ManualAllocation(usage_record_id=usage.id, department_id=engineering_dept.id, allocation_percent=Decimal("60")),
            ManualAllocation(usage_record_id=usage.id, department_id=marketing.id, allocation_percent=Decimal("40")),
        ]
    )
    db_session.commit()

    reprice_usage_record(db_session, usage)

    live = live_cost_line_items(db_session).filter(CostLineItem.usage_record_id == usage.id).all()
    # Only the two fresh manual-split rows should be "live" -- the original
    # unallocated row and its reversal are superseded, not double-counted.
    assert len(live) == 2
    assert all(li.needs_allocation is False for li in live)
    amounts_by_dept = {li.department_id: li.computed_amount for li in live}
    assert amounts_by_dept[engineering_dept.id] == Decimal("6.00")
    assert amounts_by_dept[marketing.id] == Decimal("4.00")

    # Nothing should still be flagged as needing allocation for this usage_record.
    still_needs_allocation = (
        live_cost_line_items(db_session)
        .filter(CostLineItem.usage_record_id == usage.id, CostLineItem.needs_allocation.is_(True))
        .all()
    )
    assert still_needs_allocation == []
