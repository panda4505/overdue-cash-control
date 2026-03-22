"""Customer model — the debtor who owes money."""

import uuid
from datetime import datetime, date
from typing import Any

from sqlalchemy import String, DateTime, Date, Integer, Numeric, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vat_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    company_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # IČO in Czech

    # Contact
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(5), nullable=True)

    # Aggregates (cached, updated on import)
    total_outstanding: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Matching and risk signals
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    merge_history: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    # merge_history stores confirmed alias variants as a list of dicts.
    # Example: [{"variant": "ACME SRO", "normalized_name": "acme sro", "merged_at": "2026-03-22T12:00:00Z", "match_type": "name_similarity"}]

    # Notes and state
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_paused: Mapped[bool] = mapped_column(default=False)

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    account = relationship("Account", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")
    activities = relationship("Activity", back_populates="customer")
