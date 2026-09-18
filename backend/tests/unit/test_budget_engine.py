from datetime import date
from decimal import Decimal

from app.models.allocation_map import ManualAllocation
from app.models.budget import AlertThreshold, Budget
from app.models.pricing_rate import PricingRate
from app.models.usage_record import UsageRecord, UsageSourceType
from app.services.budget_engine import current_spend_for_budget, evaluate_all_active_budgets, evaluate_budget
from app.services.costing_engine import price_usage_records


def _add_priced_usage(db, provider, department, quantity, sku="sku-x", period_start=date(2026, 1, 10)):
    if not db.query(PricingRate).filter(PricingRate.sku_code == sku).first():
        db.add(
            PricingRate(
                provider_id=provider.id,
                sku_code=sku,
                unit="per_token",
                rate_amount=Decimal("1.00"),
                effective_from=date(2026, 1, 1),
                source="test",
            )
        )
        db.commit()

    usage = UsageRecord(
        provider_id=provider.id,
        department_id=department.id,
        sku_code=sku,
        quantity=Decimal(quantity),
        unit="tokens",
        period_start=period_start,
        period_end=period_start,
        source_type=UsageSourceType.csv_import,
        source_reference="test",
    )
    db.add(usage)
    db.commit()
    db.refresh(usage)
    price_usage_records(db, [usage])
    return usage


def test_current_spend_for_budget_sums_live_line_items(db_session, anthropic_provider, engineering_dept):
    _add_priced_usage(db_session, anthropic_provider, engineering_dept, 500)
    budget = Budget(department_id=engineering_dept.id, period="2026-01", amount=Decimal("1000"))
    db_session.add(budget)
    db_session.commit()

    assert current_spend_for_budget(db_session, budget) == Decimal("500")


def test_threshold_crossing_79_to_81_to_101_fires_each_once_no_duplicates(
    db_session, anthropic_provider, engineering_dept
):
    budget = Budget(department_id=engineering_dept.id, period="2026-01", amount=Decimal("1000"))
    db_session.add(budget)
    db_session.commit()
    db_session.add_all(
        [
            AlertThreshold(budget_id=budget.id, threshold_percent=80),
            AlertThreshold(budget_id=budget.id, threshold_percent=100),
        ]
    )
    db_session.commit()

    # Spend at 79% -- no alerts yet.
    _add_priced_usage(db_session, anthropic_provider, engineering_dept, 790, sku="a")
    alerts = evaluate_budget(db_session, budget)
    assert alerts == []

    # Spend crosses to 81% -- the 80% threshold fires exactly once.
    _add_priced_usage(db_session, anthropic_provider, engineering_dept, 20, sku="b")
    alerts = evaluate_budget(db_session, budget)
    assert [a.threshold_percent for a in alerts] == [80]

    # Re-running without new spend must not re-fire the 80% threshold.
    alerts_again = evaluate_budget(db_session, budget)
    assert alerts_again == []

    # Spend crosses to 101% -- only the 100% threshold fires now (80% already fired).
    _add_priced_usage(db_session, anthropic_provider, engineering_dept, 200, sku="c")
    alerts = evaluate_budget(db_session, budget)
    assert [a.threshold_percent for a in alerts] == [100]

    # Final state: exactly one alert per threshold, ever.
    from app.models.budget import Alert

    all_alerts = db_session.query(Alert).filter(Alert.budget_id == budget.id).all()
    assert sorted(a.threshold_percent for a in all_alerts) == [80, 100]


def test_zero_amount_budget_never_divides_by_zero(db_session, engineering_dept):
    budget = Budget(department_id=engineering_dept.id, period="2026-01", amount=Decimal("0"))
    db_session.add(budget)
    db_session.commit()
    assert evaluate_budget(db_session, budget) == []


def test_evaluate_all_active_budgets_covers_multiple_departments(db_session, anthropic_provider, engineering_dept):
    from app.models.department import Department

    marketing = Department(name="Marketing", code="MKT")
    db_session.add(marketing)
    db_session.commit()

    eng_budget = Budget(department_id=engineering_dept.id, period="2026-01", amount=Decimal("100"))
    mkt_budget = Budget(department_id=marketing.id, period="2026-01", amount=Decimal("100"))
    db_session.add_all([eng_budget, mkt_budget])
    db_session.commit()
    db_session.add_all(
        [
            AlertThreshold(budget_id=eng_budget.id, threshold_percent=80),
            AlertThreshold(budget_id=mkt_budget.id, threshold_percent=80),
        ]
    )
    db_session.commit()

    _add_priced_usage(db_session, anthropic_provider, engineering_dept, 90, sku="eng-sku")
    _add_priced_usage(db_session, anthropic_provider, marketing, 10, sku="mkt-sku")

    alerts = evaluate_all_active_budgets(db_session)

    assert len(alerts) == 1
    assert alerts[0].budget_id == eng_budget.id
