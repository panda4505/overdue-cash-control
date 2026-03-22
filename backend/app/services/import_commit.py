"""Import commit service — creates pending imports and commits confirmed ones to the database."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.account import Account
from app.models.activity import Activity
from app.models.customer import Customer
from app.models.import_record import ImportRecord
from app.models.invoice import Invoice
from app.services.file_parser import parse_file
from app.services.ingestion import ingest_file
from app.services.normalization import normalize_customer_name, normalize_invoice_number

REQUIRED_TARGETS = {"invoice_number", "customer_name", "due_date"}


async def create_pending_import(
    db: AsyncSession,
    account_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    method: str = "upload",
) -> dict[str, Any]:
    """Parse a file, save it to disk, and create a pending ImportRecord."""

    result = await ingest_file(file_bytes, filename, method=method)
    parse_succeeded = bool(result.file_hash) and result.total_rows > 0

    if not parse_succeeded:
        return {
            "import_id": None,
            "preview": result.to_dict(),
            "duplicate_warning": None,
        }

    duplicate_warning = None
    duplicate_query = select(ImportRecord).where(
        ImportRecord.account_id == account_id,
        ImportRecord.file_hash == result.file_hash,
        ImportRecord.status == "confirmed",
    )
    duplicate_result = await db.execute(duplicate_query)
    existing_import = duplicate_result.scalar_one_or_none()
    if existing_import is not None:
        duplicate_warning = (
            "This file appears identical to an import from "
            f"{existing_import.created_at.strftime('%Y-%m-%d %H:%M')}. "
            "You can skip or import anyway."
        )

    settings = get_settings()
    import_id = uuid.uuid4()
    upload_dir = Path(settings.UPLOAD_DIR) / str(account_id) / str(import_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / filename
    file_path.write_bytes(file_bytes)

    import_record = ImportRecord(
        id=import_id,
        account_id=account_id,
        method=method,
        original_filename=filename,
        file_hash=result.file_hash,
        original_file_path=str(file_path),
        rows_found=result.total_rows,
        status="pending_preview",
        scope_type="unknown",
        mapping_method=result.mapping.method if result.mapping else None,
        mapping_confidence=result.mapping.overall_confidence if result.mapping else None,
        llm_tokens_used=result.mapping.llm_tokens_used if result.mapping else None,
    )
    db.add(import_record)

    try:
        await db.commit()
    except Exception:
        shutil.rmtree(upload_dir, ignore_errors=True)
        raise

    return {
        "import_id": import_id,
        "preview": result.to_dict(),
        "duplicate_warning": duplicate_warning,
    }


async def confirm_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    confirmed_mapping: dict[str, str],
) -> dict[str, Any]:
    """Confirm a pending import and commit invoices, customers, and activity."""

    import_query = select(ImportRecord).where(ImportRecord.id == import_id)
    import_result = await db.execute(import_query)
    import_record = import_result.scalar_one_or_none()

    if import_record is None:
        raise ValueError(f"Import {import_id} not found")
    if import_record.status != "pending_preview":
        raise ValueError(
            f"Import {import_id} is in state '{import_record.status}', expected 'pending_preview'"
        )

    file_path = Path(import_record.original_file_path or "")
    if not file_path.exists():
        raise ValueError(f"Stored file not found at {file_path}")

    parse_result = parse_file(file_path.read_bytes(), import_record.original_filename)
    if not parse_result.success:
        raise ValueError(f"Re-parse failed: {parse_result.error}")

    _validate_confirmed_mapping(confirmed_mapping, parse_result.headers)

    account = await _get_account(db, import_record.account_id)
    account_currency = (account.currency or "EUR").upper()

    canonical_rows = _extract_canonical_rows(parse_result, confirmed_mapping)
    if not canonical_rows:
        raise ValueError("No valid rows extracted from file")

    warnings: list[str] = []
    invoices_created = 0
    customers_created = 0
    customers_reused = 0
    errors = 0

    change_set: dict[str, list[dict[str, Any]]] = {
        "created": [],
        "updated": [],
        "disappeared": [],
        "customers_created": [],
        "customers_merged": [],
    }

    today = date.today()
    customer_cache: dict[str, Customer] = {}

    for row_index, row in enumerate(canonical_rows, start=1):
        raw_customer_name = row.get("customer_name")
        if raw_customer_name is None or str(raw_customer_name).strip() == "":
            warnings.append(f"Row {row_index}: missing customer_name, skipped")
            errors += 1
            continue

        normalized_name = normalize_customer_name(str(raw_customer_name))
        if not normalized_name:
            warnings.append(f"Row {row_index}: customer_name normalizes to empty, skipped")
            errors += 1
            continue

        raw_invoice_number = row.get("invoice_number")
        if raw_invoice_number is None or str(raw_invoice_number).strip() == "":
            warnings.append(f"Row {row_index}: missing invoice_number, skipped")
            errors += 1
            continue

        normalized_invoice_number = normalize_invoice_number(str(raw_invoice_number))

        due_date = _parse_date(row.get("due_date"))
        if due_date is None:
            warnings.append(f"Row {row_index}: invalid or missing due_date, skipped")
            errors += 1
            continue

        outstanding_amount = _parse_amount(row.get("outstanding_amount"))
        gross_amount = _parse_amount(row.get("gross_amount"))
        if outstanding_amount is None:
            if gross_amount is None:
                warnings.append(f"Row {row_index}: no outstanding or gross amount, skipped")
                errors += 1
                continue
            outstanding_amount = gross_amount
        if gross_amount is None:
            gross_amount = outstanding_amount

        customer = customer_cache.get(normalized_name)
        if customer is None:
            customer_query = select(Customer).where(
                Customer.account_id == import_record.account_id,
                Customer.normalized_name == normalized_name,
                Customer.deleted_at.is_(None),
            )
            customer_result = await db.execute(customer_query)
            customer = customer_result.scalar_one_or_none()

        if customer is None:
            customer = Customer(
                account_id=import_record.account_id,
                name=str(raw_customer_name).strip(),
                normalized_name=normalized_name,
                vat_id=_clean_optional(row.get("vat_id")),
                company_id=_clean_optional(row.get("company_id")),
                email=_clean_optional(row.get("email")),
                phone=_clean_optional(row.get("phone")),
                first_seen_at=datetime.now(timezone.utc),
            )
            db.add(customer)
            await db.flush()
            customers_created += 1
            change_set["customers_created"].append(
                {
                    "customer_id": str(customer.id),
                    "data": {
                        "name": customer.name,
                        "normalized_name": customer.normalized_name,
                        "vat_id": customer.vat_id,
                        "company_id": customer.company_id,
                        "email": customer.email,
                        "phone": customer.phone,
                    },
                }
            )
        else:
            customers_reused += 1
            if not customer.vat_id:
                customer.vat_id = _clean_optional(row.get("vat_id"))
            if not customer.company_id:
                customer.company_id = _clean_optional(row.get("company_id"))
            if not customer.email:
                customer.email = _clean_optional(row.get("email"))
            if not customer.phone:
                customer.phone = _clean_optional(row.get("phone"))

        customer_cache[normalized_name] = customer

        issue_date = _parse_date(row.get("issue_date"))
        currency = _clean_optional(row.get("currency"))
        currency = (currency or account_currency).upper()

        days_overdue = max(0, (today - due_date).days)
        first_overdue_at = due_date if days_overdue > 0 else None

        invoice = Invoice(
            account_id=import_record.account_id,
            customer_id=customer.id,
            invoice_number=str(raw_invoice_number).strip(),
            normalized_invoice_number=normalized_invoice_number,
            issue_date=issue_date,
            due_date=due_date,
            first_overdue_at=first_overdue_at,
            gross_amount=gross_amount,
            outstanding_amount=outstanding_amount,
            currency=currency,
            status="open",
            days_overdue=days_overdue,
            first_seen_import_id=import_record.id,
            last_updated_import_id=import_record.id,
        )
        db.add(invoice)
        await db.flush()
        invoices_created += 1
        change_set["created"].append(
            {
                "invoice_id": str(invoice.id),
                "data": {
                    "invoice_number": invoice.invoice_number,
                    "customer_id": str(customer.id),
                    "customer_name": customer.name,
                    "outstanding_amount": float(invoice.outstanding_amount),
                    "gross_amount": float(invoice.gross_amount),
                    "due_date": invoice.due_date.isoformat(),
                    "currency": invoice.currency,
                    "status": invoice.status,
                },
            }
        )

        customer.invoice_count = int(customer.invoice_count or 0) + 1
        customer.total_outstanding = float(customer.total_outstanding or 0) + float(outstanding_amount)
        effective_invoice_date = issue_date or due_date
        if customer.last_invoice_date is None or effective_invoice_date > customer.last_invoice_date:
            customer.last_invoice_date = effective_invoice_date

    if invoices_created == 0:
        raise ValueError("No valid rows to import")

    import_record.status = "confirmed"
    import_record.invoices_created = invoices_created
    import_record.invoices_updated = 0
    import_record.invoices_disappeared = 0
    import_record.invoices_unchanged = 0
    import_record.errors = errors
    import_record.warnings_text = json.dumps(warnings, ensure_ascii=False)
    import_record.change_set = change_set
    import_record.confirmed_at = datetime.now(timezone.utc)

    activity = Activity(
        account_id=import_record.account_id,
        import_id=import_record.id,
        action_type="import_committed",
        details={
            "method": import_record.method,
            "filename": import_record.original_filename,
            "invoices_created": invoices_created,
            "customers_created": customers_created,
            "customers_reused": customers_reused,
            "errors": errors,
        },
        performed_by="system",
    )
    db.add(activity)

    now = datetime.now(timezone.utc)
    if account.first_import_at is None:
        account.first_import_at = now
    account.last_import_at = now

    await db.commit()

    return {
        "import_id": str(import_record.id),
        "status": "confirmed",
        "invoices_created": invoices_created,
        "customers_created": customers_created,
        "customers_reused": customers_reused,
        "errors": errors,
        "warnings": warnings,
    }


def _validate_confirmed_mapping(
    confirmed_mapping: dict[str, str],
    actual_headers: list[str],
) -> None:
    """Validate the confirmed mapping before any DB writes happen."""

    header_set = set(actual_headers)

    invalid_sources = [
        source_column
        for source_column in confirmed_mapping.values()
        if source_column not in header_set
    ]
    if invalid_sources:
        raise ValueError(f"Mapping references columns not in file: {invalid_sources}")

    source_to_targets: dict[str, list[str]] = {}
    for target_field, source_column in confirmed_mapping.items():
        source_to_targets.setdefault(source_column, []).append(target_field)

    duplicated_sources = {
        source_column: targets
        for source_column, targets in source_to_targets.items()
        if len(targets) > 1
    }
    if duplicated_sources:
        raise ValueError(f"Source column(s) mapped to multiple targets: {duplicated_sources}")

    targets = set(confirmed_mapping.keys())
    missing_required = set(REQUIRED_TARGETS - targets)
    if "outstanding_amount" not in targets and "gross_amount" not in targets:
        missing_required.add("outstanding_amount or gross_amount")
    if missing_required:
        raise ValueError(f"Required fields missing from mapping: {missing_required}")


def _extract_canonical_rows(
    parse_result: Any,
    confirmed_mapping: dict[str, str],
) -> list[dict[str, Any]]:
    """Apply the confirmed mapping to all parsed rows."""

    if parse_result.dataframe is None:
        return []

    reverse_map = {source_column: target_field for target_field, source_column in confirmed_mapping.items()}
    rows: list[dict[str, Any]] = []

    for _, dataframe_row in parse_result.dataframe.iterrows():
        canonical_row: dict[str, Any] = {}
        for source_column in parse_result.dataframe.columns:
            target_field = reverse_map.get(source_column)
            if not target_field:
                continue
            value = dataframe_row[source_column]
            canonical_row[target_field] = None if pd.isna(value) else value
        rows.append(canonical_row)

    return rows


def _parse_date(value: Any) -> date | None:
    """Parse a value into a date."""

    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _parse_amount(value: Any) -> float | None:
    """Parse a value into a float amount."""

    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_optional(value: Any) -> str | None:
    """Strip optional string-like values and collapse empties to None."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


async def _get_account(db: AsyncSession, account_id: uuid.UUID) -> Account:
    """Load an account by ID."""

    account_query = select(Account).where(Account.id == account_id)
    account_result = await db.execute(account_query)
    account = account_result.scalar_one_or_none()
    if account is None:
        raise ValueError(f"Account {account_id} not found")
    return account
