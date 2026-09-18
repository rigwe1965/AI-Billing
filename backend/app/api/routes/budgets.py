from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import department_scope, ensure_department_access, get_current_user, get_db, require_admin
from app.models.budget import Alert, AlertStatus, AlertThreshold, Budget
from app.models.department import Department
from app.models.user import User
from app.schemas.budget import AlertOut, BudgetIn, BudgetOut, BudgetStatusOut
from app.services.budget_engine import current_spend_for_budget, evaluate_budget

router = APIRouter(prefix="/api/budgets", tags=["budgets"])


@router.get("", response_model=list[BudgetOut])
def list_budgets(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    query = db.query(Budget)
    if scope_department_id is not None:
        query = query.filter(Budget.department_id == scope_department_id)
    return query.all()


@router.post("", response_model=BudgetOut, dependencies=[Depends(require_admin)])
def create_budget(payload: BudgetIn, db: Session = Depends(get_db)):
    department = db.query(Department).filter(Department.code == payload.department_code).first()
    if department is None:
        raise HTTPException(404, f"Unknown department_code: {payload.department_code}")

    if db.query(Budget).filter(Budget.department_id == department.id, Budget.period == payload.period).first():
        raise HTTPException(400, f"A budget already exists for {payload.department_code} in {payload.period}")

    budget = Budget(department_id=department.id, period=payload.period, amount=payload.amount, currency=payload.currency)
    db.add(budget)
    db.commit()
    db.refresh(budget)

    for pct in payload.threshold_percents:
        db.add(AlertThreshold(budget_id=budget.id, threshold_percent=pct))
    db.commit()

    return budget


@router.get("/status", response_model=list[BudgetStatusOut])
def budget_status(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    """Current spend vs. budget for every budget the caller can see."""
    query = db.query(Budget)
    if scope_department_id is not None:
        query = query.filter(Budget.department_id == scope_department_id)

    out = []
    for budget in query.all():
        department = db.query(Department).filter(Department.id == budget.department_id).first()
        current_spend = current_spend_for_budget(db, budget)
        percent_used = (current_spend / budget.amount * 100) if budget.amount else Decimal("0")
        out.append(
            BudgetStatusOut(
                budget_id=budget.id,
                department_id=budget.department_id,
                department_name=department.name if department else "Unknown",
                period=budget.period,
                amount=budget.amount,
                current_spend=current_spend,
                percent_used=percent_used,
                currency=budget.currency,
            )
        )
    return out


@router.post("/{budget_id}/evaluate", response_model=list[AlertOut], dependencies=[Depends(require_admin)])
def evaluate_budget_now(budget_id: int, db: Session = Depends(get_db)):
    """Manually re-checks one budget's thresholds -- useful right after editing
    thresholds, without waiting for the next ingestion or the nightly job."""
    budget = db.query(Budget).filter(Budget.id == budget_id).first()
    if budget is None:
        raise HTTPException(404, f"Unknown budget_id: {budget_id}")
    return evaluate_budget(db, budget)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(
    open_only: bool = False,
    db: Session = Depends(get_db),
    scope_department_id: int | None = Depends(department_scope),
):
    query = db.query(Alert).join(Budget, Alert.budget_id == Budget.id)
    if scope_department_id is not None:
        query = query.filter(Budget.department_id == scope_department_id)
    if open_only:
        query = query.filter(Alert.status == AlertStatus.open)
    return query.order_by(Alert.triggered_at.desc()).all()


@router.post("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(404, f"Unknown alert_id: {alert_id}")

    budget = db.query(Budget).filter(Budget.id == alert.budget_id).first()
    ensure_department_access(current_user, budget.department_id)

    alert.status = AlertStatus.acknowledged
    alert.acknowledged_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(alert)
    return alert
