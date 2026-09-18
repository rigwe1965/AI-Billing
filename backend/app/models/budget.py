import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Budget(Base):
    """A department's spending ceiling for one calendar month. `period` is
    always "YYYY-MM" -- kept as a plain string so it matches the same format
    /api/costs/summary already groups by, rather than reasoning about a date
    range in two different shapes across the codebase."""

    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("department_id", "period", name="uq_budget_department_period"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    period: Mapped[str] = mapped_column(String(7), index=True)  # "YYYY-MM"
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AlertThreshold(Base):
    __tablename__ = "alert_thresholds"

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), index=True)
    threshold_percent: Mapped[int] = mapped_column()
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"


class Alert(Base):
    """One fired instance of a budget crossing a threshold. Deduplicated by
    (budget_id, threshold_percent) -- see services/budget_engine.py -- so a
    threshold only ever fires once per budget/period."""

    __tablename__ = "alerts"
    __table_args__ = (UniqueConstraint("budget_id", "threshold_percent", name="uq_alert_budget_threshold"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    budget_id: Mapped[int] = mapped_column(ForeignKey("budgets.id"), index=True)
    threshold_percent: Mapped[int] = mapped_column()
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    current_spend_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.open)
    notified_via: Mapped[str] = mapped_column(String(120), default="in_app")  # comma-separated channel names
    acknowledged_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
