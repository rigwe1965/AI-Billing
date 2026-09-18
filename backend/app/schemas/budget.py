import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

_PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class BudgetIn(BaseModel):
    department_code: str
    period: str  # "YYYY-MM"
    amount: Decimal
    currency: str = "USD"
    threshold_percents: list[int] = [80, 100]

    @field_validator("period")
    @classmethod
    def valid_period(cls, v: str) -> str:
        if not _PERIOD_RE.match(v):
            raise ValueError('period must be in "YYYY-MM" format')
        return v


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    department_id: int
    period: str
    amount: Decimal
    currency: str


class BudgetStatusOut(BaseModel):
    budget_id: int
    department_id: int
    department_name: str
    period: str
    amount: Decimal
    current_spend: Decimal
    percent_used: Decimal
    currency: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    budget_id: int
    threshold_percent: int
    triggered_at: datetime
    current_spend_amount: Decimal
    status: str
    notified_via: str
