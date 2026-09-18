"""Resolves which department(s) a usage_record's cost belongs to.

Precedence, per the build plan (never silently default to a department):
  1. usage_record.department_id already set (e.g. a dedicated per-department key
     was resolved at ingestion time, or a human entered it directly) -> direct.
  2. api_key_department_map has an active mapping for the record's api_key_label
     -> key_mapping.
  3. tag_department_map has an active mapping for the record's tag_value
     -> tag_mapping.
  4. manual_allocations exist for this usage_record -> manual_split, possibly
     across multiple departments by percentage.
  5. None of the above -> unallocated. The caller must NOT default this to any
     department; it is surfaced as "needs manual allocation" instead.
"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.allocation_map import ApiKeyDepartmentMap, ManualAllocation, TagDepartmentMap
from app.models.cost_line_item import AllocationMethod
from app.models.usage_record import UsageRecord


@dataclass(frozen=True)
class Allocation:
    department_id: int
    fraction: Decimal  # of the total cost; manual splits may be < 1 each, otherwise 1
    method: AllocationMethod
    reference_id: int | None  # id in whichever mapping table produced this allocation


def resolve_allocations(db: Session, usage_record: UsageRecord) -> list[Allocation]:
    if usage_record.department_id is not None:
        return [
            Allocation(
                department_id=usage_record.department_id,
                fraction=Decimal("1"),
                method=AllocationMethod.direct,
                reference_id=None,
            )
        ]

    on_date = usage_record.period_start

    if usage_record.api_key_label:
        key_map = (
            db.query(ApiKeyDepartmentMap)
            .filter(
                ApiKeyDepartmentMap.provider_id == usage_record.provider_id,
                ApiKeyDepartmentMap.api_key_label == usage_record.api_key_label,
                ApiKeyDepartmentMap.effective_from <= on_date,
            )
            .filter(
                (ApiKeyDepartmentMap.effective_to.is_(None))
                | (ApiKeyDepartmentMap.effective_to >= on_date)
            )
            .order_by(ApiKeyDepartmentMap.effective_from.desc())
            .first()
        )
        if key_map:
            return [
                Allocation(
                    department_id=key_map.department_id,
                    fraction=Decimal("1"),
                    method=AllocationMethod.key_mapping,
                    reference_id=key_map.id,
                )
            ]

    if usage_record.tag_value:
        tag_map = (
            db.query(TagDepartmentMap)
            .filter(
                TagDepartmentMap.provider_id == usage_record.provider_id,
                TagDepartmentMap.tag_value == usage_record.tag_value,
                TagDepartmentMap.effective_from <= on_date,
            )
            .filter(
                (TagDepartmentMap.effective_to.is_(None)) | (TagDepartmentMap.effective_to >= on_date)
            )
            .order_by(TagDepartmentMap.effective_from.desc())
            .first()
        )
        if tag_map:
            return [
                Allocation(
                    department_id=tag_map.department_id,
                    fraction=Decimal("1"),
                    method=AllocationMethod.tag_mapping,
                    reference_id=tag_map.id,
                )
            ]

    manual_rows = (
        db.query(ManualAllocation)
        .filter(ManualAllocation.usage_record_id == usage_record.id)
        .all()
    )
    if manual_rows:
        return [
            Allocation(
                department_id=row.department_id,
                fraction=Decimal(row.allocation_percent) / Decimal("100"),
                method=AllocationMethod.manual_split,
                reference_id=row.id,
            )
            for row in manual_rows
        ]

    return []
