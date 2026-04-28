from sqlalchemy import String, Integer, Numeric, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPrimaryKeyMixin, TimestampMixin


class Venue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "venues"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_per_head_usd: Mapped[float | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    venue_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amenities: Mapped[dict] = mapped_column(JSONB, default=list, server_default="[]")
    tags: Mapped[dict] = mapped_column(JSONB, default=list, server_default="[]")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    policies: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    documents = relationship("Document", back_populates="venue", lazy="selectin")

    __table_args__ = (
        Index("ix_venues_amenities", "amenities", postgresql_using="gin"),
        Index("ix_venues_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name='{self.name}', city='{self.city}')>"