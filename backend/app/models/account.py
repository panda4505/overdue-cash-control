"""Account model — the company using the product."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Paris")
    language: Mapped[str] = mapped_column(String(5), nullable=False, default="en")

    # Email ingestion
    resend_inbound_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sending_domain_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="not_configured"
    )  # not_configured, pending, verified

    # Activation & retention signals
    first_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_import_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_recovered_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    users = relationship("User", back_populates="account")
    customers = relationship("Customer", back_populates="account")
    invoices = relationship("Invoice", back_populates="account")
    imports = relationship("ImportRecord", back_populates="account")
    templates = relationship("ImportTemplate", back_populates="account")
    activities = relationship("Activity", back_populates="account")
