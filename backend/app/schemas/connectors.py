from datetime import date

from pydantic import BaseModel


class ConnectorStatusOut(BaseModel):
    provider_code: str
    configured: bool
    supports_usage_pull: bool
    supports_cost_reconciliation: bool
    requires_prerequisite: str | None
    unavailable_reason: str | None


class ConnectionTestOut(BaseModel):
    provider_code: str
    ok: bool
    detail: str


class PullRequest(BaseModel):
    period_start: date
    period_end: date


class PullResult(BaseModel):
    usage_records_created: int
    cost_line_items_created: int
    needs_pricing_rule_count: int
    needs_allocation_count: int
