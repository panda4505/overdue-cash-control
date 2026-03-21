"""ImportTemplate model — saved column mappings for repeat imports."""

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ImportTemplate(Base):
    __tablename__ = "import_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scope type — hard rule: only full_snapshot can drive disappearance logic
    scope_type: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    # full_snapshot | partial | unknown

    # Column mapping
    column_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # column_mapping structure:
    # {
    #   "invoice_number": "Numero fattura",     # or "Numéro de facture", "Číslo faktury", "Invoice Number"
    #   "customer_name": "Ragione sociale",     # or "Nom du client", "Odběratel", "Client Name"
    #   "due_date": "Data scadenza",            # or "Date d'échéance", "Datum splatnosti", "Due Date"
    #   "gross_amount": "Importo lordo",        # or "Montant TTC", "Celkem s DPH", "Total Amount"
    #   "outstanding_amount": "Importo residuo", # or "Reste à payer", "Zbývá uhradit", "Amount Due"
    #   "currency": "Valuta",                   # or "Devise", "Měna", "Currency"
    #   "email": "Email",
    #   ...
    # }

    # File format hints
    delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)  # , or ;
    date_format: Mapped[str | None] = mapped_column(String(30), nullable=True)  # DD.MM.YYYY etc.
    decimal_separator: Mapped[str | None] = mapped_column(String(5), nullable=True)  # "." or ","
    thousands_separator: Mapped[str | None] = mapped_column(String(5), nullable=True)  # " ", ".", ",", or None
    encoding: Mapped[str | None] = mapped_column(String(30), nullable=True)  # utf-8, windows-1250

    # Usage tracking
    times_used: Mapped[int] = mapped_column(default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    account = relationship("Account", back_populates="templates")
    imports = relationship("ImportRecord", back_populates="template")
