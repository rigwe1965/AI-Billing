"""Common contract every provider connector implements.

A connector's only job is to fetch raw usage from a provider and normalize it
into RawUsageRecord -- it never computes cost or resolves department
allocation. That keeps API-pulled usage flowing through the exact same
costing_engine / allocation_service code path as CSV-imported usage.

capabilities() exists because provider API availability is genuinely uncertain
(see docs/provider-connector-notes.md) -- callers must check it and fall back
to CSV import/manual entry rather than assuming fetch_usage() will succeed.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ConnectorCapabilities:
    supports_usage_pull: bool
    supports_cost_reconciliation: bool  # provider also reports its own $ cost, for cross-checking
    requires_prerequisite: str | None = None  # e.g. "Cloud Billing export to BigQuery enabled"
    unavailable_reason: str | None = None  # set when credentials missing / feature detected off


@dataclass(frozen=True)
class RawUsageRecord:
    sku_code: str
    quantity: Decimal
    unit: str
    period_start: date
    period_end: date
    api_key_label: str | None = None
    tag_value: str | None = None
    provider_reported_amount: Decimal | None = None  # for reconciliation only, never authoritative
    raw_payload_ref: str | None = None


@dataclass(frozen=True)
class ConnectionStatus:
    ok: bool
    detail: str


class ConnectorUnavailableError(RuntimeError):
    """Raised when fetch_usage() is called but capabilities().supports_usage_pull
    is False -- callers should catch this and prompt for CSV import instead."""


class AbstractProviderConnector(ABC):
    provider_code: str

    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities:
        ...

    @abstractmethod
    def test_connection(self) -> ConnectionStatus:
        ...

    @abstractmethod
    def fetch_usage(self, period_start: date, period_end: date) -> list[RawUsageRecord]:
        ...
