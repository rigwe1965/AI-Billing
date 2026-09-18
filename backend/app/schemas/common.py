from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    is_active: bool


class ProviderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    connector_type: str


class PricingRateIn(BaseModel):
    provider_code: str
    sku_code: str
    unit: str
    rate_amount: Decimal
    currency: str = "USD"
    effective_from: date
    source: str = "manual_admin_entry"


class PricingRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    provider_id: int
    sku_code: str
    unit: str
    rate_amount: Decimal
    currency: str
    effective_from: date
    effective_to: date | None
    source: str


class CsvImportResult(BaseModel):
    usage_records_created: int
    cost_line_items_created: int
    needs_pricing_rule_count: int


class CostSummaryRow(BaseModel):
    period: str
    department: str | None
    provider: str
    total_amount: Decimal
    currency: str


class UnpricedUsageRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cost_line_item_id: int
    usage_record_id: int
    provider: str
    sku_code: str
    quantity: Decimal
    period_start: date
    reason: str
