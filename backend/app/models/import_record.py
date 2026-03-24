"""ImportRecord model — every file import with full audit trail and rollback data."""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, DateTime, Integer, Text, ForeignKey, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportRecord(Base):
    __tablename__ = "import_records"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )

    # Source
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # upload | email
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 for duplicate detection
    original_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # path to stored original

    # Email metadata (only for method=email)
    email_sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resend_email_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Template and scope
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("import_templates.id"), nullable=True
    )
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    # full_snapshot | partial | unknown

    # Results
    rows_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invoices_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invoices_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invoices_disappeared: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invoices_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    # pending_preview | confirmed | rolled_back | cancelled | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_preview")

    # Rollback data — structured change set
    change_set: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # change_set structure:
    # {
    #   "created": [{"invoice_id": "...", "data": {...}}],
    #   "updated": [{"invoice_id": "...", "before": {...}, "after": {...}}],
    #   "disappeared": [{"invoice_id": "...", "before": {...}}],
    #   "customers_created": [{"customer_id": "...", "data": {...}}],
    #   "customers_merged": [{"customer_id": "...", "variant": "...", "merged_into": "..."}]
    # }

    # Performance and cost tracking
    parse_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mapping_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # deterministic | template | llm
    mapping_confidence: Mapped[float | None] = mapped_column(nullable=True)
    llm_tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    account = relationship("Account", back_populates="imports")
    template = relationship("ImportTemplate", back_populates="imports")
    activities = relationship("Activity", back_populates="import_record")

    __table_args__ = (
        Index("ix_imports_account_status", "account_id", "status"),
        Index("ix_imports_file_hash", "account_id", "file_hash"),
    )
