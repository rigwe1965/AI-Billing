from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class ApiKeyMapIn(BaseModel):
    provider_code: str
    api_key_label: str
    department_code: str
    effective_from: date


class ApiKeyMapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider_id: int
    api_key_label: str
    department_id: int
    effective_from: date
    effective_to: date | None


class TagMapIn(BaseModel):
    provider_code: str
    tag_value: str
    department_code: str
    effective_from: date


class TagMapOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider_id: int
    tag_value: str
    department_id: int
    effective_from: date
    effective_to: date | None


class ManualAllocationSplit(BaseModel):
    department_code: str
    allocation_percent: Decimal


class ManualAllocationIn(BaseModel):
    usage_record_id: int
    splits: list[ManualAllocationSplit]
    note: str | None = None

    @field_validator("splits")
    @classmethod
    def percents_sum_to_100(cls, splits: list[ManualAllocationSplit]):
        if not splits:
            raise ValueError("At least one split is required")
        total = sum(s.allocation_percent for s in splits)
        if total != Decimal("100"):
            raise ValueError(f"allocation_percent values must sum to 100, got {total}")
        return splits


class ManualAllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    usage_record_id: int
    department_id: int
    allocation_percent: Decimal
    note: str | None
