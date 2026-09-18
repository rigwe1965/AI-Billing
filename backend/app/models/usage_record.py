import enum
from datetime import date, datetime, timezone

from sqlalchemy import String, Numeric, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UsageSourceType(str, enum.Enum):
    api_pull = "api_pull"
    csv_import = "csv_import"
    manual_entry = "manual_entry"


class UsageRecord(Base):
    """A raw, unpriced usage fact. Costing engine consumes these; it never mutates them."""

    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    sku_code: Mapped[str] = mapped_column(String(120), index=True)
    quantity: Mapped[Numeric] = mapped_column(Numeric(18, 6))
    unit: Mapped[str] = mapped_column(String(40))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    source_type: Mapped[UsageSourceType] = mapped_column(Enum(UsageSourceType))
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key_label: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tag_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    imported_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
