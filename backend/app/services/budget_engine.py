"""Evaluates budgets against actual spend and fires alerts on newly-crossed
thresholds. Called both (a) immediately after any ingestion/costing batch
(CSV import, connector pull, manual allocation reprice) and (b) nightly as a
safety net -- see app/jobs/scheduler.py.

Dedup: a unique constraint on (budget_id, threshold_percent) means a threshold
fires exactly once for a given budget/period, however many times this runs.
"""

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.budget import Alert, AlertThreshold, Budget
from app.models.cost_line_item import CostLineItem
from app.models.department import Department
from app.models.usage_record import UsageRecord
from app.services import notification_service
from app.services.costing_engine import live_cost_line_items


def current_spend_for_budget(db: Session, budget: Budget) -> Decimal:
    total = (
        live_cost_line_items(db)
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .filter(
            CostLineItem.department_id == budget.department_id,
            CostLineItem.computed_amount.isnot(None),
            func.strftime("%Y-%m", UsageRecord.period_start) == budget.period,
        )
        .with_entities(func.sum(CostLineItem.computed_amount))
        .scalar()
    )
    return Decimal(total) if total is not None else Decimal("0")


def evaluate_budget(db: Session, budget: Budget) -> list[Alert]:
    current_spend = current_spend_for_budget(db, budget)
    if budget.amount == 0:
        return []
    spend_percent = (current_spend / budget.amount) * 100

    thresholds = (
        db.query(AlertThreshold)
        .filter(AlertThreshold.budget_id == budget.id, AlertThreshold.is_active.is_(True))
        .all()
    )
    already_fired = {
        a.threshold_percent for a in db.query(Alert).filter(Alert.budget_id == budget.id).all()
    }

    department = db.query(Department).filter(Department.id == budget.department_id).first()
    new_alerts = []
    for threshold in sorted(thresholds, key=lambda t: t.threshold_percent):
        if threshold.threshold_percent in already_fired:
            continue
        if spend_percent < threshold.threshold_percent:
            continue

        alert = Alert(
            budget_id=budget.id,
            threshold_percent=threshold.threshold_percent,
            current_spend_amount=current_spend,
            notified_via="",
        )
        db.add(alert)
        db.flush()  # assign alert.id before dispatch/commit
        sent_via = notification_service.dispatch(alert, department)
        alert.notified_via = ",".join(sent_via)
        new_alerts.append(alert)
        already_fired.add(threshold.threshold_percent)

    if new_alerts:
        db.commit()
        for a in new_alerts:
            db.refresh(a)
    return new_alerts


def evaluate_all_active_budgets(db: Session) -> list[Alert]:
    return [alert for budget in db.query(Budget).all() for alert in evaluate_budget(db, budget)]
