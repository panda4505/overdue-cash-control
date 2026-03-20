"""Activity model — timeline of everything that happens in an account."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False
    )

    # What this activity relates to (all optional — some activities are account-level)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    import_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_records.id"), nullable=True
    )

    # Action type
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # import_committed | import_rolled_back
    # invoice_created | invoice_updated | invoice_disappeared | invoice_recovered
    # reminder_sent | reminder_drafted
    # call_logged | promise_recorded | promise_expired
    # dispute_opened | dispute_resolved
    # status_changed | paused | resumed | escalated
    # customer_created | customer_merged
    # note_added

    # Details — flexible JSONB for action-specific data
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # details examples:
    # {"from_status": "open", "to_status": "promised", "promise_date": "2026-04-01"}
    # {"reminder_type": "first", "recipient": "info@acme.cz", "send_method": "model_a"}
    # {"old_balance": 5000, "new_balance": 3000, "import_id": "..."}
    # {"merged_variant": "ACME SRO", "merged_into_customer": "..."}

    # Who performed this (account-level in v1, future: user-level)
    performed_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # "system" for automated actions, "user" for manual, user_id later

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    account = relationship("Account", back_populates="activities")
    invoice = relationship("Invoice", back_populates="activities")
    customer = relationship("Customer", back_populates="activities")
    import_record = relationship("ImportRecord", back_populates="activities")

    __table_args__ = (
        Index("ix_activities_account_created", "account_id", "created_at"),
        Index("ix_activities_invoice", "invoice_id", "created_at"),
        Index("ix_activities_customer", "customer_id", "created_at"),
        Index("ix_activities_type", "account_id", "action_type"),
    )
