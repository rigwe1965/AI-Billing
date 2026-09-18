from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import String, Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApiKeyDepartmentMap(Base):
    """One provider API key belongs to exactly one department for a date range.

    Never store the raw secret key here -- only a human-readable label
    (e.g. last 4 chars) that usage_records.api_key_label can be matched against.
    """

    __tablename__ = "api_key_department_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    api_key_label: Mapped[str] = mapped_column(String(120), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class TagDepartmentMap(Base):
    """A shared account's usage is tagged (project id / customer id / workspace id);
    this maps a tag value to the department that owns it, for a date range."""

    __tablename__ = "tag_department_map"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    tag_value: Mapped[str] = mapped_column(String(120), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class ManualAllocation(Base):
    """A human-entered split of one usage_record's cost across department(s),
    used when neither key mapping nor tag mapping applies. Multiple rows for the
    same usage_record_id represent a percentage split; percentages should sum to 100."""

    __tablename__ = "manual_allocations"

    id: Mapped[int] = mapped_column(primary_key=True)
    usage_record_id: Mapped[int] = mapped_column(ForeignKey("usage_records.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    allocation_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
