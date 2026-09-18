import enum

from sqlalchemy import String, Enum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProviderCode(str, enum.Enum):
    anthropic = "anthropic"
    openai = "openai"
    google = "google"
    custom = "custom"


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    code: Mapped[ProviderCode] = mapped_column(Enum(ProviderCode))
    connector_type: Mapped[str] = mapped_column(String(60), default="manual")
