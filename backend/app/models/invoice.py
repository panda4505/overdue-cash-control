"""Invoice model — the core record the entire product revolves around."""

import uuid
from datetime import datetime, date

from sqlalchemy import (
    String, DateTime, Date, Integer, Numeric, Text,
    ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )

    # Invoice identity
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    normalized_invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)

    # Dates
    issue_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    first_overdue_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Money
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    outstanding_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CZK")

    # Status
    # open | promised | disputed | paused | escalated | possibly_paid | recovered | closed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Action tracking
    last_action_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_action_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Data lineage
    first_seen_import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_records.id"), nullable=True
    )
    last_updated_import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_records.id"), nullable=True
    )

    # Recovery tracking
    recovery_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recovery_import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_records.id"), nullable=True
    )

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    account = relationship("Account", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    activities = relationship("Activity", back_populates="invoice")

    # Indexes for action queue and dashboard queries
    __table_args__ = (
        Index("ix_invoices_account_status", "account_id", "status"),
        Index("ix_invoices_account_due", "account_id", "due_date"),
        Index("ix_invoices_account_invoice_num", "account_id", "normalized_invoice_number"),
        Index("ix_invoices_next_action", "account_id", "next_action_date"),
    )
