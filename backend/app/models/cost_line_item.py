import enum
from datetime import datetime, timezone

from sqlalchemy import Numeric, DateTime, ForeignKey, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AllocationMethod(str, enum.Enum):
    direct = "direct"
    key_mapping = "key_mapping"
    tag_mapping = "tag_mapping"
    manual_split = "manual_split"
    unallocated = "unallocated"


class CostLineItem(Base):
    """The audit-trail row: usage provenance + pricing provenance + allocation outcome.

    Append-only. A correction is a new reversal row referencing the original via
    `reverses_line_item_id`, never an UPDATE to computed_amount.
    """

    __tablename__ = "cost_line_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    usage_record_id: Mapped[int] = mapped_column(ForeignKey("usage_records.id"))
    pricing_rate_id: Mapped[int | None] = mapped_column(ForeignKey("pricing_rates.id"), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    computed_amount: Mapped[Numeric | None] = mapped_column(Numeric(12, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    allocation_method: Mapped[AllocationMethod] = mapped_column(Enum(AllocationMethod))
    needs_pricing_rule: Mapped[bool] = mapped_column(default=False)
    needs_allocation: Mapped[bool] = mapped_column(default=False)
    # Points at api_key_department_map.id / tag_department_map.id / manual_allocations.id
    # depending on allocation_method -- not a single-table FK since it's polymorphic.
    allocation_reference_id: Mapped[int | None] = mapped_column(nullable=True)
    reverses_line_item_id: Mapped[int | None] = mapped_column(ForeignKey("cost_line_items.id"), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    computed_by: Mapped[str] = mapped_column(String(60), default="system:costing_engine_v1")
