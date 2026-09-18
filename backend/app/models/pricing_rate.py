from datetime import date

from sqlalchemy import String, Numeric, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingRate(Base):
    """A versioned, human-maintained price for one SKU over an effective date range.

    Never updated in place: a price change closes the old row's effective_to and
    inserts a new row. This is what makes every cost figure re-derivable and auditable.
    """

    __tablename__ = "pricing_rates"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"))
    sku_code: Mapped[str] = mapped_column(String(120), index=True)
    unit: Mapped[str] = mapped_column(String(40))  # e.g. per_1k_tokens, per_seat_month, per_request
    rate_amount: Mapped[Numeric] = mapped_column(Numeric(12, 6))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(255))  # e.g. "manual_admin_entry" or "config_file:anthropic_2026-01-01.yaml"
    created_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
