from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.allocation_map import ApiKeyDepartmentMap, ManualAllocation, TagDepartmentMap
from app.models.cost_line_item import CostLineItem
from app.models.department import Department
from app.models.provider import Provider
from app.models.usage_record import UsageRecord
from app.schemas.allocation import (
    ApiKeyMapIn,
    ApiKeyMapOut,
    ManualAllocationIn,
    ManualAllocationOut,
    TagMapIn,
    TagMapOut,
)
from app.services.budget_engine import evaluate_all_active_budgets
from app.services.costing_engine import reprice_usage_record

router = APIRouter(prefix="/api/allocations", tags=["allocations"])


def _get_provider(db: Session, provider_code: str) -> Provider:
    provider = db.query(Provider).filter(Provider.code == provider_code).first()
    if provider is None:
        raise HTTPException(404, f"Unknown provider_code: {provider_code}")
    return provider


def _get_department(db: Session, department_code: str) -> Department:
    dept = db.query(Department).filter(Department.code == department_code).first()
    if dept is None:
        raise HTTPException(404, f"Unknown department_code: {department_code}")
    return dept


@router.get("/api-key-map", response_model=list[ApiKeyMapOut], dependencies=[Depends(require_admin)])
def list_api_key_maps(db: Session = Depends(get_db)):
    return db.query(ApiKeyDepartmentMap).all()


@router.post("/api-key-map", response_model=ApiKeyMapOut, dependencies=[Depends(require_admin)])
def create_api_key_map(payload: ApiKeyMapIn, db: Session = Depends(get_db)):
    provider = _get_provider(db, payload.provider_code)
    department = _get_department(db, payload.department_code)
    mapping = ApiKeyDepartmentMap(
        provider_id=provider.id,
        api_key_label=payload.api_key_label,
        department_id=department.id,
        effective_from=payload.effective_from,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.get("/tag-map", response_model=list[TagMapOut], dependencies=[Depends(require_admin)])
def list_tag_maps(db: Session = Depends(get_db)):
    return db.query(TagDepartmentMap).all()


@router.post("/tag-map", response_model=TagMapOut, dependencies=[Depends(require_admin)])
def create_tag_map(payload: TagMapIn, db: Session = Depends(get_db)):
    provider = _get_provider(db, payload.provider_code)
    department = _get_department(db, payload.department_code)
    mapping = TagDepartmentMap(
        provider_id=provider.id,
        tag_value=payload.tag_value,
        department_id=department.id,
        effective_from=payload.effective_from,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.post("/manual", response_model=list[ManualAllocationOut], dependencies=[Depends(require_admin)])
def create_manual_allocation(payload: ManualAllocationIn, db: Session = Depends(get_db)):
    """Splits one usage_record's cost across departments by percentage, then
    immediately reprices it: the prior unallocated (or stale) line item is
    reversed and new department-attributed line items are created."""
    usage_record = db.query(UsageRecord).filter(UsageRecord.id == payload.usage_record_id).first()
    if usage_record is None:
        raise HTTPException(404, f"Unknown usage_record_id: {payload.usage_record_id}")

    rows = []
    for split in payload.splits:
        department = _get_department(db, split.department_code)
        rows.append(
            ManualAllocation(
                usage_record_id=usage_record.id,
                department_id=department.id,
                allocation_percent=split.allocation_percent,
                note=payload.note,
            )
        )
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)

    reprice_usage_record(db, usage_record)
    evaluate_all_active_budgets(db)
    return rows


@router.post("/reprocess-unallocated", dependencies=[Depends(require_admin)])
def reprocess_unallocated(db: Session = Depends(get_db)):
    """Re-resolves department allocation for every usage_record currently stuck
    as needs_allocation, using whatever key/tag/manual mappings exist now. Useful
    after adding a mapping that should retroactively cover older usage."""
    stuck_usage_record_ids = {
        row[0]
        for row in db.query(CostLineItem.usage_record_id)
        .filter(CostLineItem.needs_allocation.is_(True))
        .all()
    }
    resolved_count = 0
    for usage_record_id in stuck_usage_record_ids:
        usage_record = db.query(UsageRecord).filter(UsageRecord.id == usage_record_id).first()
        new_items = reprice_usage_record(db, usage_record)
        if not any(li.needs_allocation for li in new_items):
            resolved_count += 1

    evaluate_all_active_budgets(db)
    return {"checked": len(stuck_usage_record_ids), "resolved": resolved_count}
