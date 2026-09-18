from sqlalchemy import func
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import department_scope, get_db
from app.models.cost_line_item import CostLineItem
from app.models.department import Department
from app.models.provider import Provider
from app.models.usage_record import UsageRecord
from app.schemas.common import CostSummaryRow, UnpricedUsageRow
from app.services.costing_engine import live_cost_line_items

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("/summary", response_model=list[CostSummaryRow])
def cost_summary(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    """Total priced spend grouped by month/provider/department, computed from
    only the *live* cost_line_items (reversed/superseded rows excluded -- see
    services.costing_engine.live_cost_line_items). needs_pricing_rule rows are
    excluded here too and surfaced separately via /unpriced.
    A dept_lead only ever sees rows for their own department; admin_finance
    (scope_department_id is None) sees everything.
    """
    live_ids = live_cost_line_items(db).with_entities(CostLineItem.id)
    query = (
        db.query(
            func.strftime("%Y-%m", UsageRecord.period_start).label("period"),
            Department.name.label("department"),
            Provider.name.label("provider"),
            func.sum(CostLineItem.computed_amount).label("total_amount"),
            CostLineItem.currency.label("currency"),
        )
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .join(Provider, UsageRecord.provider_id == Provider.id)
        .outerjoin(Department, CostLineItem.department_id == Department.id)
        .filter(CostLineItem.id.in_(live_ids))
        .filter(CostLineItem.computed_amount.isnot(None))
    )
    if scope_department_id is not None:
        query = query.filter(CostLineItem.department_id == scope_department_id)

    rows = query.group_by("period", "department", "provider", CostLineItem.currency).order_by("period").all()
    return [
        CostSummaryRow(
            period=r.period,
            department=r.department,
            provider=r.provider,
            total_amount=r.total_amount,
            currency=r.currency,
        )
        for r in rows
    ]


@router.get("/unpriced", response_model=list[UnpricedUsageRow])
def unpriced_usage(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    """Live usage the costing engine refused to guess a price for — needs a
    pricing_rate added. A dept_lead sees only their own department's; admin sees all.
    """
    query = (
        live_cost_line_items(db)
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .join(Provider, UsageRecord.provider_id == Provider.id)
        .filter(CostLineItem.needs_pricing_rule.is_(True))
        .with_entities(CostLineItem, UsageRecord, Provider)
    )
    if scope_department_id is not None:
        query = query.filter(CostLineItem.department_id == scope_department_id)

    return [
        UnpricedUsageRow(
            cost_line_item_id=cli.id,
            usage_record_id=ur.id,
            provider=provider.name,
            sku_code=ur.sku_code,
            quantity=ur.quantity,
            period_start=ur.period_start,
            reason="No active pricing_rate found for this provider/sku/date",
        )
        for cli, ur, provider in query.all()
    ]


@router.get("/needs-allocation", response_model=list[UnpricedUsageRow])
def needs_allocation_usage(db: Session = Depends(get_db), scope_department_id: int | None = Depends(department_scope)):
    """Live usage priced (or unpriced) but with no resolved department -- never
    silently assigned. Only admin_finance can see this: a dept_lead has nothing
    to act on here since these rows aren't attributed to any department yet.
    """
    if scope_department_id is not None:
        return []

    rows = (
        live_cost_line_items(db)
        .join(UsageRecord, CostLineItem.usage_record_id == UsageRecord.id)
        .join(Provider, UsageRecord.provider_id == Provider.id)
        .filter(CostLineItem.needs_allocation.is_(True))
        .with_entities(CostLineItem, UsageRecord, Provider)
        .all()
    )
    return [
        UnpricedUsageRow(
            cost_line_item_id=cli.id,
            usage_record_id=ur.id,
            provider=provider.name,
            sku_code=ur.sku_code,
            quantity=ur.quantity,
            period_start=ur.period_start,
            reason="No key/tag/manual mapping resolved a department for this usage",
        )
        for cli, ur, provider in rows
    ]
