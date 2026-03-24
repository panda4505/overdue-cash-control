"""Import commit service — creates pending imports and commits confirmed ones to the database."""

from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.account import Account
from app.models.activity import Activity
from app.models.customer import Customer
from app.models.import_record import ImportRecord
from app.models.invoice import Invoice
from app.services.anomaly_detection import (
    Anomaly,
    anomaly_to_dict,
    detect_customer_anomalies,
    detect_invoice_anomalies,
)
from app.services.customer_matching import (
    ExistingCustomerInfo,
    FileCustomer,
    find_best_match,
    find_fuzzy_matches,
    fuzzy_match_result_to_dict,
)
from app.services.file_parser import parse_file
from app.services.ingestion import ingest_file
from app.services.normalization import normalize_customer_name, normalize_invoice_number


@dataclass(frozen=True)
class ExistingInvoiceSnapshot:
    """Immutable snapshot of a DB invoice for the planner. No ORM references."""

    id: str
    normalized_invoice_number: str
    invoice_number: str
    customer_id: str
    outstanding_amount: float
    gross_amount: float
    due_date: date
    issue_date: date | None
    currency: str
    status: str
    first_overdue_at: date | None


@dataclass(frozen=True)
class ExistingCustomerSnapshot:
    """Immutable snapshot of a DB customer for the planner. No ORM references."""

    id: str
    name: str
    normalized_name: str
    vat_id: str | None
    company_id: str | None
    email: str | None
    phone: str | None
    merge_history: list[dict[str, Any]] | None


@dataclass
class PlannedNewCustomer:
    """A customer the plan intends to create. placeholder_id is internal only."""

    placeholder_id: str
    raw_name: str
    normalized_name: str
    vat_id: str | None
    company_id: str | None
    email: str | None
    phone: str | None


@dataclass
class PlannedCreatedInvoice:
    invoice_number: str
    customer_name: str
    outstanding_amount: float
    gross_amount: float
    due_date: str
    issue_date: str | None
    currency: str
    customer_ref: str
    is_new_customer: bool
    source_vat_id: str | None = None
    source_company_id: str | None = None
    source_email: str | None = None
    source_phone: str | None = None


@dataclass
class PlannedUpdatedInvoice:
    invoice_id: str
    normalized_invoice_number: str
    invoice_number: str
    customer_name: str
    customer_ref: str
    changes: dict[str, dict[str, Any]]
    before_snapshot: dict[str, Any]
    after_snapshot: dict[str, Any]
    source_vat_id: str | None = None
    source_company_id: str | None = None
    source_email: str | None = None
    source_phone: str | None = None


@dataclass
class PlannedDisappearedInvoice:
    invoice_id: str
    invoice_number: str
    customer_name: str
    outstanding_amount: float
    days_overdue: int
    previous_status: str


@dataclass
class PlannedCustomerResolution:
    file_name: str
    resolved_to: str
    resolution_type: str
    score: float | None
    is_new: bool


@dataclass
class PlannedCustomerMerge:
    file_name: str
    merged_into: str
    match_type: str
    target_customer_id: str
    normalized_name: str
    source_vat_id: str | None = None
    source_company_id: str | None = None
    source_email: str | None = None
    source_phone: str | None = None


@dataclass
class PlannedUnchangedInvoice:
    """Internal-only refresh data for unchanged invoices."""

    invoice_id: str


@dataclass
class ImportPlan:
    created_invoices: list[PlannedCreatedInvoice] = field(default_factory=list)
    updated_invoices: list[PlannedUpdatedInvoice] = field(default_factory=list)
    disappeared_invoices: list[PlannedDisappearedInvoice] = field(default_factory=list)
    invoices_unchanged: int = 0
    new_customers: list[PlannedNewCustomer] = field(default_factory=list)
    customer_resolutions: list[PlannedCustomerResolution] = field(default_factory=list)
    customer_merges: list[PlannedCustomerMerge] = field(default_factory=list)
    customers_reused: int = 0
    anomalies: list[Anomaly] = field(default_factory=list)
    skipped_rows: int = 0
    warnings: list[str] = field(default_factory=list)
    total_new_amount: float = 0.0
    total_disappeared_amount: float = 0.0
    unchanged_invoices: list[PlannedUnchangedInvoice] = field(
        default_factory=list,
        repr=False,
    )
    resolved_customer_refs: set[str] = field(default_factory=set, repr=False)
    reassigned_old_customer_ids: set[str] = field(default_factory=set, repr=False)


@dataclass
class ImportContext:
    """All data needed for planning and applying an import."""

    import_record: ImportRecord
    account: Any
    account_currency: str
    canonical_rows: list[dict[str, Any]]
    invoice_snapshots: dict[str, ExistingInvoiceSnapshot]
    ambiguous_normalized_numbers: set[str]
    incoming_duplicates: set[str]
    customer_snapshots: dict[str, ExistingCustomerSnapshot]
    customer_snapshots_by_id: dict[str, ExistingCustomerSnapshot]
    merge_history_index: dict[str, str]
    existing_customer_infos: list[ExistingCustomerInfo]
    resolved_merge_ids: dict[str, str]
    pre_import_overdue_counts: dict[str, int]
    orm_invoices_by_normalized: dict[str, Invoice]
    orm_invoices_by_id: dict[str, Invoice]
    orm_customers_by_id: dict[str, Customer]
    orm_customers_by_normalized: dict[str, Customer]


REQUIRED_TARGETS = {"invoice_number", "customer_name", "due_date"}


async def create_pending_import(
    db: AsyncSession,
    account_id: uuid.UUID,
    file_bytes: bytes,
    filename: str,
    method: str = "upload",
    template_mapping: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Parse a file, save it to disk, and create a pending ImportRecord."""

    result = await ingest_file(
        file_bytes, filename, method=method, existing_template=template_mapping
    )
    parse_succeeded = bool(result.file_hash) and result.total_rows > 0

    if not parse_succeeded:
        return {
            "import_id": None,
            "preview": result.to_dict(),
            "duplicate_warning": None,
            "fuzzy_matches": None,
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

    fuzzy_matches_preview: dict[str, Any] | None = None
    try:
        fuzzy_matches_preview = await _compute_fuzzy_preview(db, account_id, result)
    except Exception:
        pass

    return {
        "import_id": import_id,
        "preview": result.to_dict(),
        "duplicate_warning": duplicate_warning,
        "fuzzy_matches": fuzzy_matches_preview,
    }


async def prepare_import_context(
    db: AsyncSession,
    import_id: uuid.UUID,
    confirmed_mapping: dict[str, str],
    scope_type: str = "unknown",
    merge_decisions: dict[str, str] | None = None,
) -> ImportContext:
    """Shared preparation for preview and confirm: load, validate, index, snapshot."""

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

    existing_invoices_query = select(Invoice).where(
        Invoice.account_id == import_record.account_id,
        Invoice.deleted_at.is_(None),
    )
    existing_invoices_result = await db.execute(existing_invoices_query)
    existing_invoices_list = existing_invoices_result.scalars().all()

    existing_invoice_map: dict[str, Invoice] = {}
    ambiguous_normalized_numbers: set[str] = set()
    for invoice in existing_invoices_list:
        if invoice.normalized_invoice_number in existing_invoice_map:
            ambiguous_normalized_numbers.add(invoice.normalized_invoice_number)
        else:
            existing_invoice_map[invoice.normalized_invoice_number] = invoice

    for normalized_number in ambiguous_normalized_numbers:
        existing_invoice_map.pop(normalized_number, None)

    incoming_normalized: dict[str, int] = {}
    incoming_duplicates: set[str] = set()
    for row_index, row in enumerate(canonical_rows, start=1):
        raw_invoice_number = row.get("invoice_number")
        if raw_invoice_number is None or str(raw_invoice_number).strip() == "":
            continue
        normalized_number = normalize_invoice_number(str(raw_invoice_number))
        if normalized_number in incoming_normalized:
            incoming_duplicates.add(normalized_number)
        else:
            incoming_normalized[normalized_number] = row_index

    existing_customers_query = select(Customer).where(
        Customer.account_id == import_record.account_id,
        Customer.deleted_at.is_(None),
    )
    existing_customers_result = await db.execute(existing_customers_query)
    existing_customers_list = existing_customers_result.scalars().all()

    orm_customers_by_normalized: dict[str, Customer] = {}
    orm_customers_by_id: dict[str, Customer] = {}
    for customer in existing_customers_list:
        orm_customers_by_normalized[customer.normalized_name] = customer
        orm_customers_by_id[str(customer.id)] = customer

    merge_history_idx: dict[str, str] = {}
    for customer in existing_customers_list:
        if isinstance(customer.merge_history, list):
            for entry in customer.merge_history:
                normalized_variant = entry.get("normalized_name")
                if normalized_variant:
                    merge_history_idx[normalized_variant] = str(customer.id)

    existing_customer_infos: list[ExistingCustomerInfo] = []
    for customer in existing_customers_list:
        info = ExistingCustomerInfo(
            customer_id=str(customer.id),
            normalized_name=customer.normalized_name,
            display_name=customer.name,
            vat_id=customer.vat_id,
            merge_history=customer.merge_history if isinstance(customer.merge_history, list) else None,
        )
        existing_customer_infos.append(info)

    resolved_merge_ids: dict[str, str] = {}
    if merge_decisions:
        for normalized_name, customer_id in merge_decisions.items():
            target = orm_customers_by_id.get(customer_id)
            if target is None:
                raise ValueError(
                    f"merge_decisions references unknown customer ID '{customer_id}' "
                    f"for name '{normalized_name}'. Customer must exist and belong to this account."
                )
            resolved_merge_ids[normalized_name] = customer_id

    invoice_snapshots: dict[str, ExistingInvoiceSnapshot] = {}
    for normalized_number, invoice in existing_invoice_map.items():
        invoice_snapshots[normalized_number] = ExistingInvoiceSnapshot(
            id=str(invoice.id),
            normalized_invoice_number=invoice.normalized_invoice_number,
            invoice_number=invoice.invoice_number,
            customer_id=str(invoice.customer_id),
            outstanding_amount=float(invoice.outstanding_amount),
            gross_amount=float(invoice.gross_amount),
            due_date=invoice.due_date,
            issue_date=invoice.issue_date,
            currency=invoice.currency,
            status=invoice.status,
            first_overdue_at=invoice.first_overdue_at,
        )

    customer_snapshots: dict[str, ExistingCustomerSnapshot] = {}
    customer_snapshots_by_id: dict[str, ExistingCustomerSnapshot] = {}
    for customer in existing_customers_list:
        snapshot = ExistingCustomerSnapshot(
            id=str(customer.id),
            name=customer.name,
            normalized_name=customer.normalized_name,
            vat_id=customer.vat_id,
            company_id=customer.company_id,
            email=customer.email,
            phone=customer.phone,
            merge_history=customer.merge_history if isinstance(customer.merge_history, list) else None,
        )
        customer_snapshots[customer.normalized_name] = snapshot
        customer_snapshots_by_id[str(customer.id)] = snapshot

    today = date.today()
    pre_import_overdue_counts: dict[str, int] = {}
    for customer in existing_customers_list:
        count = 0
        for invoice in existing_invoices_list:
            if (
                invoice.customer_id == customer.id
                and invoice.status == "open"
                and invoice.due_date is not None
                and invoice.due_date < today
            ):
                count += 1
        pre_import_overdue_counts[str(customer.id)] = count

    return ImportContext(
        import_record=import_record,
        account=account,
        account_currency=account_currency,
        canonical_rows=canonical_rows,
        invoice_snapshots=invoice_snapshots,
        ambiguous_normalized_numbers=ambiguous_normalized_numbers,
        incoming_duplicates=incoming_duplicates,
        customer_snapshots=customer_snapshots,
        customer_snapshots_by_id=customer_snapshots_by_id,
        merge_history_index=merge_history_idx,
        existing_customer_infos=existing_customer_infos,
        resolved_merge_ids=resolved_merge_ids,
        pre_import_overdue_counts=pre_import_overdue_counts,
        orm_invoices_by_normalized=existing_invoice_map,
        orm_invoices_by_id={
            str(invoice.id): invoice
            for invoice in existing_invoices_list
            if invoice.normalized_invoice_number not in ambiguous_normalized_numbers
        },
        orm_customers_by_id=orm_customers_by_id,
        orm_customers_by_normalized=orm_customers_by_normalized,
    )


def build_import_plan(
    canonical_rows: list[dict[str, Any]],
    invoice_snapshots: dict[str, ExistingInvoiceSnapshot],
    ambiguous_normalized_numbers: set[str],
    incoming_duplicates: set[str],
    customer_snapshots: dict[str, ExistingCustomerSnapshot],
    customer_snapshots_by_id: dict[str, ExistingCustomerSnapshot],
    merge_history_index: dict[str, str],
    existing_customer_infos: list[ExistingCustomerInfo],
    resolved_merge_ids: dict[str, str],
    pre_import_overdue_counts: dict[str, int],
    account_currency: str,
    scope_type: str,
) -> ImportPlan:
    """Build a pure import plan from snapshot data with no ORM side effects."""

    plan = ImportPlan()
    today = date.today()

    seen_invoice_numbers: set[str] = set()
    resolved_customers: dict[str, tuple[str, str, bool]] = {}
    recorded_customer_resolutions: set[str] = set()
    new_customer_placeholder_ids: set[str] = set()
    invoice_snapshots_by_id = {snapshot.id: snapshot for snapshot in invoice_snapshots.values()}

    customer_display_by_ref: dict[str, str] = {
        customer_id: snapshot.name
        for customer_id, snapshot in customer_snapshots_by_id.items()
    }

    working_existing_customer_infos = [
        ExistingCustomerInfo(
            customer_id=info.customer_id,
            normalized_name=info.normalized_name,
            display_name=info.display_name,
            vat_id=info.vat_id,
            merge_history=list(info.merge_history) if isinstance(info.merge_history, list) else None,
        )
        for info in existing_customer_infos
    ]
    working_existing_customer_info_by_id = {
        info.customer_id: info for info in working_existing_customer_infos
    }
    working_merge_history_index = dict(merge_history_index)

    for row_index, row in enumerate(canonical_rows, start=1):
        raw_customer_name = row.get("customer_name")
        if raw_customer_name is None or str(raw_customer_name).strip() == "":
            plan.warnings.append(f"Row {row_index}: missing customer_name, skipped")
            plan.skipped_rows += 1
            continue

        normalized_name = normalize_customer_name(str(raw_customer_name))
        if not normalized_name:
            plan.warnings.append(f"Row {row_index}: customer_name normalizes to empty, skipped")
            plan.skipped_rows += 1
            continue

        raw_invoice_number = row.get("invoice_number")
        if raw_invoice_number is None or str(raw_invoice_number).strip() == "":
            plan.warnings.append(f"Row {row_index}: missing invoice_number, skipped")
            plan.skipped_rows += 1
            continue

        due_date = _parse_date(row.get("due_date"))
        if due_date is None:
            plan.warnings.append(f"Row {row_index}: invalid or missing due_date, skipped")
            plan.skipped_rows += 1
            continue

        outstanding_amount = _parse_amount(row.get("outstanding_amount"))
        gross_amount = _parse_amount(row.get("gross_amount"))
        if outstanding_amount is None:
            if gross_amount is None:
                plan.warnings.append(f"Row {row_index}: no outstanding or gross amount, skipped")
                plan.skipped_rows += 1
                continue
            outstanding_amount = gross_amount
        if gross_amount is None:
            gross_amount = outstanding_amount

        source_vat_id = _clean_optional(row.get("vat_id"))
        source_company_id = _clean_optional(row.get("company_id"))
        source_email = _clean_optional(row.get("email"))
        source_phone = _clean_optional(row.get("phone"))

        normalized_invoice_number = normalize_invoice_number(str(raw_invoice_number))

        if normalized_invoice_number in ambiguous_normalized_numbers:
            plan.warnings.append(
                f"Row {row_index}: invoice number '{raw_invoice_number}' matches multiple "
                f"existing invoices (ambiguous), skipped"
            )
            plan.skipped_rows += 1
            continue

        if (
            normalized_invoice_number in incoming_duplicates
            and normalized_invoice_number in seen_invoice_numbers
        ):
            plan.warnings.append(
                f"Row {row_index}: duplicate invoice number '{raw_invoice_number}' in file, skipped"
            )
            plan.skipped_rows += 1
            continue

        seen_invoice_numbers.add(normalized_invoice_number)

        issue_date = _parse_date(row.get("issue_date"))
        currency = (_clean_optional(row.get("currency")) or account_currency).upper()

        customer_ref: str | None = None
        customer_name: str | None = None
        is_new_customer = False
        created_new_customer_this_row = False
        resolution_type: str | None = None
        resolution_score: float | None = None
        merge_match_type: str | None = None
        should_record_merge = False

        cached_resolution = resolved_customers.get(normalized_name)
        if cached_resolution is not None:
            customer_ref, customer_name, is_new_customer = cached_resolution
        else:
            exact_snapshot = customer_snapshots.get(normalized_name)
            if exact_snapshot is not None:
                customer_ref = exact_snapshot.id
                customer_name = exact_snapshot.name
                resolution_type = "exact"
            else:
                history_customer_id = working_merge_history_index.get(normalized_name)
                if history_customer_id is not None:
                    customer_ref = history_customer_id
                    customer_name = customer_display_by_ref.get(history_customer_id, "Unknown")
                    resolution_type = "merge_history"

            if customer_ref is None:
                file_customer = FileCustomer(
                    normalized_name=normalized_name,
                    raw_name=str(raw_customer_name).strip(),
                    vat_id=source_vat_id,
                )
                match = find_best_match(file_customer, working_existing_customer_infos)

                if match is not None:
                    if match.confidence == "high":
                        customer_ref = match.existing_customer_id
                        customer_name = match.existing_customer_name
                        resolution_type = match.match_type
                        resolution_score = match.score
                        if match.match_type != "merge_history":
                            should_record_merge = True
                            merge_match_type = match.match_type
                    elif match.confidence == "medium":
                        decision_customer_id = resolved_merge_ids.get(normalized_name)
                        if decision_customer_id is not None:
                            customer_ref = decision_customer_id
                            customer_name = customer_display_by_ref.get(
                                decision_customer_id,
                                match.existing_customer_name,
                            )
                            resolution_type = "user_confirmed"
                            resolution_score = match.score
                            should_record_merge = True
                            merge_match_type = "user_confirmed"

            if customer_ref is None:
                placeholder_id = f"planned-new-{normalized_name}"
                planned_customer = PlannedNewCustomer(
                    placeholder_id=placeholder_id,
                    raw_name=str(raw_customer_name).strip(),
                    normalized_name=normalized_name,
                    vat_id=source_vat_id,
                    company_id=source_company_id,
                    email=source_email,
                    phone=source_phone,
                )
                plan.new_customers.append(planned_customer)
                created_new_customer_this_row = True
                customer_ref = placeholder_id
                customer_name = planned_customer.raw_name
                is_new_customer = True
                resolution_type = "new"

                new_info = ExistingCustomerInfo(
                    customer_id=placeholder_id,
                    normalized_name=planned_customer.normalized_name,
                    display_name=planned_customer.raw_name,
                    vat_id=planned_customer.vat_id,
                    merge_history=None,
                )
                working_existing_customer_infos.append(new_info)
                working_existing_customer_info_by_id[placeholder_id] = new_info
                customer_display_by_ref[placeholder_id] = planned_customer.raw_name
                new_customer_placeholder_ids.add(placeholder_id)

            resolved_customers[normalized_name] = (
                customer_ref,
                customer_name or str(raw_customer_name).strip(),
                is_new_customer,
            )

        if customer_ref is None or customer_name is None:
            plan.warnings.append(
                f"Row {row_index}: customer resolution failed for '{raw_customer_name}', skipped"
            )
            plan.skipped_rows += 1
            continue

        if normalized_name not in recorded_customer_resolutions:
            plan.customer_resolutions.append(
                PlannedCustomerResolution(
                    file_name=str(raw_customer_name).strip(),
                    resolved_to=customer_name,
                    resolution_type=resolution_type or ("new" if is_new_customer else "exact"),
                    score=resolution_score,
                    is_new=is_new_customer,
                )
            )
            recorded_customer_resolutions.add(normalized_name)

        existing_info = working_existing_customer_info_by_id.get(customer_ref)
        if existing_info is not None and existing_info.vat_id is None and source_vat_id is not None:
            existing_info.vat_id = source_vat_id

        if should_record_merge and merge_match_type is not None:
            plan.customer_merges.append(
                PlannedCustomerMerge(
                    file_name=str(raw_customer_name).strip(),
                    merged_into=customer_name,
                    match_type=merge_match_type,
                    target_customer_id=customer_ref,
                    normalized_name=normalized_name,
                    source_vat_id=source_vat_id,
                    source_company_id=source_company_id,
                    source_email=source_email,
                    source_phone=source_phone,
                )
            )

            merge_entry = {
                "variant": str(raw_customer_name).strip(),
                "normalized_name": normalized_name,
                "merged_at": datetime.now(timezone.utc).isoformat(),
                "match_type": merge_match_type,
            }
            if existing_info is not None:
                existing_history = existing_info.merge_history or []
                existing_info.merge_history = existing_history + [merge_entry]
            working_merge_history_index[normalized_name] = customer_ref

        if not created_new_customer_this_row:
            plan.customers_reused += 1

        plan.resolved_customer_refs.add(customer_ref)

        existing_invoice = invoice_snapshots.get(normalized_invoice_number)
        if existing_invoice is not None:
            changes: dict[str, dict[str, Any]] = {}

            if float(existing_invoice.outstanding_amount) != float(outstanding_amount):
                changes["outstanding_amount"] = {
                    "before": float(existing_invoice.outstanding_amount),
                    "after": float(outstanding_amount),
                }
            if float(existing_invoice.gross_amount) != float(gross_amount):
                changes["gross_amount"] = {
                    "before": float(existing_invoice.gross_amount),
                    "after": float(gross_amount),
                }
            if existing_invoice.due_date != due_date:
                changes["due_date"] = {
                    "before": existing_invoice.due_date.isoformat(),
                    "after": due_date.isoformat(),
                }
            if existing_invoice.issue_date != issue_date:
                changes["issue_date"] = {
                    "before": existing_invoice.issue_date.isoformat()
                    if existing_invoice.issue_date
                    else None,
                    "after": issue_date.isoformat() if issue_date else None,
                }
            if existing_invoice.currency != currency:
                changes["currency"] = {
                    "before": existing_invoice.currency,
                    "after": currency,
                }
            if existing_invoice.customer_id != customer_ref:
                changes["customer_id"] = {
                    "before": str(existing_invoice.customer_id),
                    "after": customer_ref,
                }
                plan.reassigned_old_customer_ids.add(existing_invoice.customer_id)
            if existing_invoice.status == "possibly_paid":
                changes["status"] = {
                    "before": "possibly_paid",
                    "after": "open",
                }

            plan.anomalies.extend(
                detect_invoice_anomalies(
                    invoice_id=existing_invoice.id,
                    customer_id=customer_ref,
                    invoice_number=existing_invoice.invoice_number,
                    existing_status=existing_invoice.status,
                    existing_outstanding=float(existing_invoice.outstanding_amount),
                    new_outstanding=float(outstanding_amount),
                    existing_due_date=existing_invoice.due_date,
                    new_due_date=due_date,
                )
            )

            if changes:
                after_status = "open" if existing_invoice.status == "possibly_paid" else existing_invoice.status
                before_snapshot = {
                    "outstanding_amount": float(existing_invoice.outstanding_amount),
                    "gross_amount": float(existing_invoice.gross_amount),
                    "due_date": existing_invoice.due_date.isoformat(),
                    "issue_date": existing_invoice.issue_date.isoformat()
                    if existing_invoice.issue_date
                    else None,
                    "currency": existing_invoice.currency,
                    "customer_id": str(existing_invoice.customer_id),
                    "status": existing_invoice.status,
                }
                after_snapshot = {
                    "outstanding_amount": float(outstanding_amount),
                    "gross_amount": float(gross_amount),
                    "due_date": due_date.isoformat(),
                    "issue_date": issue_date.isoformat() if issue_date else None,
                    "currency": currency,
                    "customer_id": customer_ref,
                    "status": after_status,
                }
                plan.updated_invoices.append(
                    PlannedUpdatedInvoice(
                        invoice_id=existing_invoice.id,
                        normalized_invoice_number=existing_invoice.normalized_invoice_number,
                        invoice_number=existing_invoice.invoice_number,
                        customer_name=customer_name,
                        customer_ref=customer_ref,
                        changes=changes,
                        before_snapshot=before_snapshot,
                        after_snapshot=after_snapshot,
                        source_vat_id=source_vat_id,
                        source_company_id=source_company_id,
                        source_email=source_email,
                        source_phone=source_phone,
                    )
                )
            else:
                plan.invoices_unchanged += 1
                plan.unchanged_invoices.append(
                    PlannedUnchangedInvoice(invoice_id=existing_invoice.id)
                )
        else:
            plan.created_invoices.append(
                PlannedCreatedInvoice(
                    invoice_number=str(raw_invoice_number).strip(),
                    customer_name=customer_name,
                    outstanding_amount=float(outstanding_amount),
                    gross_amount=float(gross_amount),
                    due_date=due_date.isoformat(),
                    issue_date=issue_date.isoformat() if issue_date else None,
                    currency=currency,
                    customer_ref=customer_ref,
                    is_new_customer=is_new_customer,
                    source_vat_id=source_vat_id,
                    source_company_id=source_company_id,
                    source_email=source_email,
                    source_phone=source_phone,
                )
            )
            plan.total_new_amount += float(outstanding_amount)

    if scope_type == "full_snapshot":
        active_statuses = {"open", "promised", "disputed", "paused", "escalated"}
        for normalized_number, existing_invoice in invoice_snapshots.items():
            if normalized_number in seen_invoice_numbers:
                continue
            if existing_invoice.status not in active_statuses:
                continue

            customer_name = customer_display_by_ref.get(existing_invoice.customer_id, "Unknown")
            plan.disappeared_invoices.append(
                PlannedDisappearedInvoice(
                    invoice_id=existing_invoice.id,
                    invoice_number=existing_invoice.invoice_number,
                    customer_name=customer_name,
                    outstanding_amount=float(existing_invoice.outstanding_amount),
                    days_overdue=max(0, (today - existing_invoice.due_date).days),
                    previous_status=existing_invoice.status,
                )
            )
            plan.total_disappeared_amount += float(existing_invoice.outstanding_amount)

    post_overdue_counts = dict(pre_import_overdue_counts)
    affected_customer_refs = set(plan.resolved_customer_refs) | set(plan.reassigned_old_customer_ids)

    for planned_new_customer in plan.new_customers:
        post_overdue_counts.setdefault(planned_new_customer.placeholder_id, 0)

    for created_invoice in plan.created_invoices:
        post_overdue_counts.setdefault(created_invoice.customer_ref, 0)
        created_due_date = _parse_date(created_invoice.due_date)
        if created_due_date is not None and created_due_date < today:
            post_overdue_counts[created_invoice.customer_ref] += 1

    for disappeared_invoice in plan.disappeared_invoices:
        existing_invoice = invoice_snapshots_by_id.get(disappeared_invoice.invoice_id)
        if existing_invoice is None:
            continue
        affected_customer_refs.add(existing_invoice.customer_id)
        post_overdue_counts.setdefault(
            existing_invoice.customer_id,
            pre_import_overdue_counts.get(existing_invoice.customer_id, 0),
        )
        if existing_invoice.status == "open" and existing_invoice.due_date < today:
            post_overdue_counts[existing_invoice.customer_id] = max(
                0,
                post_overdue_counts[existing_invoice.customer_id] - 1,
            )

    for updated_invoice in plan.updated_invoices:
        before_customer_id = str(updated_invoice.before_snapshot["customer_id"])
        after_customer_ref = updated_invoice.customer_ref
        affected_customer_refs.add(before_customer_id)
        affected_customer_refs.add(after_customer_ref)

        post_overdue_counts.setdefault(
            before_customer_id,
            pre_import_overdue_counts.get(before_customer_id, 0),
        )
        post_overdue_counts.setdefault(
            after_customer_ref,
            pre_import_overdue_counts.get(after_customer_ref, 0),
        )

        before_due_date = _parse_date(updated_invoice.before_snapshot.get("due_date"))
        after_due_date = _parse_date(updated_invoice.after_snapshot.get("due_date"))
        before_is_overdue = (
            updated_invoice.before_snapshot.get("status") == "open"
            and before_due_date is not None
            and before_due_date < today
        )
        after_is_overdue = (
            updated_invoice.after_snapshot.get("status") == "open"
            and after_due_date is not None
            and after_due_date < today
        )

        if before_customer_id == after_customer_ref:
            if before_is_overdue and not after_is_overdue:
                post_overdue_counts[before_customer_id] = max(
                    0,
                    post_overdue_counts[before_customer_id] - 1,
                )
            elif after_is_overdue and not before_is_overdue:
                post_overdue_counts[before_customer_id] += 1
        else:
            if before_is_overdue:
                post_overdue_counts[before_customer_id] = max(
                    0,
                    post_overdue_counts[before_customer_id] - 1,
                )
            if after_is_overdue:
                post_overdue_counts[after_customer_ref] += 1

    for customer_ref in affected_customer_refs:
        customer_name = customer_display_by_ref.get(customer_ref, "Unknown")
        plan.anomalies.extend(
            detect_customer_anomalies(
                customer_id=customer_ref,
                customer_name=customer_name,
                pre_overdue_count=pre_import_overdue_counts.get(customer_ref, 0),
                post_overdue_count=post_overdue_counts.get(customer_ref, 0),
                is_new_customer=customer_ref in new_customer_placeholder_ids,
            )
        )

    return plan


async def preview_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    confirmed_mapping: dict[str, str],
    scope_type: str = "unknown",
    merge_decisions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Preview the business diff without committing. Returns structured plan."""

    ctx = await prepare_import_context(db, import_id, confirmed_mapping, scope_type, merge_decisions)

    plan = build_import_plan(
        canonical_rows=ctx.canonical_rows,
        invoice_snapshots=ctx.invoice_snapshots,
        ambiguous_normalized_numbers=ctx.ambiguous_normalized_numbers,
        incoming_duplicates=ctx.incoming_duplicates,
        customer_snapshots=ctx.customer_snapshots,
        customer_snapshots_by_id=ctx.customer_snapshots_by_id,
        merge_history_index=ctx.merge_history_index,
        existing_customer_infos=ctx.existing_customer_infos,
        resolved_merge_ids=ctx.resolved_merge_ids,
        pre_import_overdue_counts=ctx.pre_import_overdue_counts,
        account_currency=ctx.account_currency,
        scope_type=scope_type,
    )

    return _serialize_preview(plan, scope_type)


def _serialize_preview(plan: ImportPlan, scope_type: str) -> dict[str, Any]:
    """Serialize an ImportPlan to the preview API response."""

    return {
        "preview_generated_at": datetime.now(timezone.utc).isoformat(),
        "invoices_created": len(plan.created_invoices),
        "invoices_updated": len(plan.updated_invoices),
        "invoices_disappeared": len(plan.disappeared_invoices),
        "invoices_unchanged": plan.invoices_unchanged,
        "customers_created": len(plan.new_customers),
        "customers_reused": plan.customers_reused,
        "customers_merged": len(plan.customer_merges),
        "skipped_rows": plan.skipped_rows,
        "warnings": plan.warnings,
        "anomalies_flagged": len(plan.anomalies),
        "total_new_amount": plan.total_new_amount,
        "total_disappeared_amount": plan.total_disappeared_amount,
        "scope_type": scope_type,
        "created_invoices": [
            {
                "invoice_number": invoice.invoice_number,
                "customer_name": invoice.customer_name,
                "outstanding_amount": invoice.outstanding_amount,
                "due_date": invoice.due_date,
                "currency": invoice.currency,
            }
            for invoice in plan.created_invoices
        ],
        "updated_invoices": [
            {
                "invoice_number": invoice.invoice_number,
                "customer_name": invoice.customer_name,
                "changes": invoice.changes,
            }
            for invoice in plan.updated_invoices
        ],
        "disappeared_invoices": [
            {
                "invoice_number": invoice.invoice_number,
                "customer_name": invoice.customer_name,
                "outstanding_amount": invoice.outstanding_amount,
                "days_overdue": invoice.days_overdue,
            }
            for invoice in plan.disappeared_invoices
        ],
        "anomalies": [_serialize_preview_anomaly(anomaly) for anomaly in plan.anomalies],
        "customer_resolutions": [
            {
                "file_name": resolution.file_name,
                "resolved_to": resolution.resolved_to,
                "resolution_type": resolution.resolution_type,
                "score": resolution.score,
                "is_new": resolution.is_new,
            }
            for resolution in plan.customer_resolutions
        ],
        "customers_merged_detail": [
            {
                "file_name": merge.file_name,
                "merged_into": merge.merged_into,
                "match_type": merge.match_type,
            }
            for merge in plan.customer_merges
        ],
    }


PREVIEW_ANOMALY_SAFE_DETAIL_KEYS = {
    "invoice_number",
    "customer_name",
    "previous_amount",
    "new_amount",
    "increase",
    "previous_due_date",
    "new_due_date",
    "previous_status",
    "restored_to",
    "previous_overdue_count",
    "new_overdue_count",
    "delta",
    "overdue_invoice_count",
}


def _serialize_preview_anomaly(anomaly: Anomaly) -> dict[str, Any]:
    """Serialize an anomaly for the preview API response."""

    safe_details = {
        key: value
        for key, value in anomaly.details.items()
        if key in PREVIEW_ANOMALY_SAFE_DETAIL_KEYS
    }
    result: dict[str, Any] = {
        "anomaly_type": anomaly.anomaly_type,
        "details": safe_details,
    }
    if "invoice_number" in safe_details:
        result["invoice_number"] = safe_details["invoice_number"]
    if "customer_name" in safe_details:
        result["customer_name"] = safe_details["customer_name"]
    return result


async def confirm_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    confirmed_mapping: dict[str, str],
    scope_type: str = "unknown",
    merge_decisions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Confirm a pending import: plan then apply."""

    ctx = await prepare_import_context(db, import_id, confirmed_mapping, scope_type, merge_decisions)

    plan = build_import_plan(
        canonical_rows=ctx.canonical_rows,
        invoice_snapshots=ctx.invoice_snapshots,
        ambiguous_normalized_numbers=ctx.ambiguous_normalized_numbers,
        incoming_duplicates=ctx.incoming_duplicates,
        customer_snapshots=ctx.customer_snapshots,
        customer_snapshots_by_id=ctx.customer_snapshots_by_id,
        merge_history_index=ctx.merge_history_index,
        existing_customer_infos=ctx.existing_customer_infos,
        resolved_merge_ids=ctx.resolved_merge_ids,
        pre_import_overdue_counts=ctx.pre_import_overdue_counts,
        account_currency=ctx.account_currency,
        scope_type=scope_type,
    )

    if (len(plan.created_invoices) + len(plan.updated_invoices) + plan.invoices_unchanged) == 0:
        raise ValueError("No valid rows to import")

    await _apply_import_plan(db, ctx, plan, scope_type)

    return {
        "import_id": str(ctx.import_record.id),
        "status": "confirmed",
        "scope_type": scope_type,
        "invoices_created": len(plan.created_invoices),
        "invoices_updated": len(plan.updated_invoices),
        "invoices_disappeared": len(plan.disappeared_invoices),
        "invoices_unchanged": plan.invoices_unchanged,
        "customers_created": len(plan.new_customers),
        "customers_reused": plan.customers_reused,
        "customers_merged": len(plan.customer_merges),
        "skipped_rows": plan.skipped_rows,
        "warnings": plan.warnings,
        "anomalies_flagged": len(plan.anomalies),
        "anomalies": [anomaly_to_dict(anomaly) for anomaly in plan.anomalies],
    }


async def _apply_import_plan(
    db: AsyncSession,
    ctx: ImportContext,
    plan: ImportPlan,
    scope_type: str,
) -> None:
    """Apply a planned import to the database without re-running business matching."""

    placeholder_to_real_customer_ids: dict[str, uuid.UUID] = {}
    change_set: dict[str, list[dict[str, Any]]] = {
        "created": [],
        "updated": [],
        "disappeared": [],
        "customers_created": [],
        "customers_merged": [],
        "anomalies": [],
    }

    now = datetime.now(timezone.utc)

    for planned_customer in plan.new_customers:
        customer = Customer(
            account_id=ctx.import_record.account_id,
            name=planned_customer.raw_name,
            normalized_name=planned_customer.normalized_name,
            vat_id=planned_customer.vat_id,
            company_id=planned_customer.company_id,
            email=planned_customer.email,
            phone=planned_customer.phone,
            first_seen_at=now,
        )
        db.add(customer)
        await db.flush()

        placeholder_to_real_customer_ids[planned_customer.placeholder_id] = customer.id
        ctx.orm_customers_by_id[str(customer.id)] = customer
        ctx.orm_customers_by_normalized[customer.normalized_name] = customer

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

    def resolve_customer_ref(ref: str) -> uuid.UUID:
        if ref.startswith("planned-new-"):
            resolved = placeholder_to_real_customer_ids.get(ref)
            if resolved is None:
                raise ValueError(f"Unable to resolve planned customer reference '{ref}'")
            return resolved
        return uuid.UUID(ref)

    merged_customer_ids = {merge.target_customer_id for merge in plan.customer_merges}

    for planned_merge in plan.customer_merges:
        resolved_target_customer_id = resolve_customer_ref(planned_merge.target_customer_id)
        customer = ctx.orm_customers_by_id.get(str(resolved_target_customer_id))
        if customer is None:
            raise ValueError(
                f"Planned merge references unknown customer ID '{planned_merge.target_customer_id}'"
            )

        _backfill_customer_contact_fields(
            customer,
            vat_id=planned_merge.source_vat_id,
            company_id=planned_merge.source_company_id,
            email=planned_merge.source_email,
            phone=planned_merge.source_phone,
        )

        existing_history = customer.merge_history if isinstance(customer.merge_history, list) else []
        customer.merge_history = existing_history + [
            {
                "variant": planned_merge.file_name,
                "normalized_name": planned_merge.normalized_name,
                "merged_at": datetime.now(timezone.utc).isoformat(),
                "match_type": planned_merge.match_type,
            }
        ]

        change_set["customers_merged"].append(
            {
                "customer_id": str(customer.id),
                "variant": planned_merge.file_name,
                "merged_into": customer.name,
                "match_type": planned_merge.match_type,
            }
        )

        db.add(
            Activity(
                account_id=ctx.import_record.account_id,
                import_id=ctx.import_record.id,
                customer_id=customer.id,
                action_type="customer_merged",
                details={
                    "merged_variant": planned_merge.file_name,
                    "merged_into_customer": str(customer.id),
                    "merged_into_name": customer.name,
                    "match_type": planned_merge.match_type,
                },
                performed_by="system",
            )
        )

    backfilled_customer_ids: set[str] = set()
    for planned_invoice in [*plan.created_invoices, *plan.updated_invoices]:
        if planned_invoice.customer_ref.startswith("planned-new-"):
            continue
        if planned_invoice.customer_ref in merged_customer_ids:
            continue
        if planned_invoice.customer_ref in backfilled_customer_ids:
            continue

        customer = ctx.orm_customers_by_id.get(planned_invoice.customer_ref)
        if customer is None:
            continue

        _backfill_customer_contact_fields(
            customer,
            vat_id=planned_invoice.source_vat_id,
            company_id=planned_invoice.source_company_id,
            email=planned_invoice.source_email,
            phone=planned_invoice.source_phone,
        )
        backfilled_customer_ids.add(planned_invoice.customer_ref)

    today = date.today()

    for planned_invoice in plan.created_invoices:
        customer_id = resolve_customer_ref(planned_invoice.customer_ref)
        due_date = _parse_date(planned_invoice.due_date)
        if due_date is None:
            raise ValueError(
                f"Planned created invoice '{planned_invoice.invoice_number}' has invalid due_date"
            )
        issue_date = _parse_date(planned_invoice.issue_date)
        days_overdue = max(0, (today - due_date).days)
        first_overdue_at = due_date if days_overdue > 0 else None

        invoice = Invoice(
            account_id=ctx.import_record.account_id,
            customer_id=customer_id,
            invoice_number=planned_invoice.invoice_number,
            normalized_invoice_number=normalize_invoice_number(planned_invoice.invoice_number),
            issue_date=issue_date,
            due_date=due_date,
            first_overdue_at=first_overdue_at,
            gross_amount=planned_invoice.gross_amount,
            outstanding_amount=planned_invoice.outstanding_amount,
            currency=planned_invoice.currency,
            status="open",
            days_overdue=days_overdue,
            first_seen_import_id=ctx.import_record.id,
            last_updated_import_id=ctx.import_record.id,
        )
        db.add(invoice)
        await db.flush()

        change_set["created"].append(
            {
                "invoice_id": str(invoice.id),
                "data": {
                    "invoice_number": invoice.invoice_number,
                    "customer_id": str(customer_id),
                    "customer_name": planned_invoice.customer_name,
                    "outstanding_amount": float(invoice.outstanding_amount),
                    "gross_amount": float(invoice.gross_amount),
                    "due_date": invoice.due_date.isoformat(),
                    "currency": invoice.currency,
                    "status": invoice.status,
                },
            }
        )

    for planned_invoice in plan.updated_invoices:
        invoice = ctx.orm_invoices_by_id.get(planned_invoice.invoice_id)
        if invoice is None:
            raise ValueError(
                f"Planned updated invoice '{planned_invoice.invoice_id}' no longer exists"
            )

        before_snapshot = {
            "outstanding_amount": float(invoice.outstanding_amount),
            "gross_amount": float(invoice.gross_amount),
            "due_date": invoice.due_date.isoformat(),
            "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
            "currency": invoice.currency,
            "customer_id": str(invoice.customer_id),
            "status": invoice.status,
        }

        resolved_customer_id = resolve_customer_ref(planned_invoice.customer_ref)
        due_date = _parse_date(planned_invoice.after_snapshot.get("due_date"))
        if due_date is None:
            raise ValueError(
                f"Planned updated invoice '{planned_invoice.invoice_number}' has invalid due_date"
            )
        issue_date = _parse_date(planned_invoice.after_snapshot.get("issue_date"))
        days_overdue = max(0, (today - due_date).days)

        invoice.outstanding_amount = float(planned_invoice.after_snapshot["outstanding_amount"])
        invoice.gross_amount = float(planned_invoice.after_snapshot["gross_amount"])
        invoice.due_date = due_date
        invoice.issue_date = issue_date
        invoice.currency = str(planned_invoice.after_snapshot["currency"])
        invoice.customer_id = resolved_customer_id
        invoice.days_overdue = days_overdue
        invoice.last_updated_import_id = ctx.import_record.id
        invoice.status = str(planned_invoice.after_snapshot["status"])

        if invoice.first_overdue_at is None and days_overdue > 0:
            invoice.first_overdue_at = due_date

        after_snapshot = {
            "outstanding_amount": float(invoice.outstanding_amount),
            "gross_amount": float(invoice.gross_amount),
            "due_date": invoice.due_date.isoformat(),
            "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
            "currency": invoice.currency,
            "customer_id": str(invoice.customer_id),
            "status": invoice.status,
        }

        change_set["updated"].append(
            {
                "invoice_id": str(invoice.id),
                "invoice_number": planned_invoice.invoice_number,
                "before": before_snapshot,
                "after": after_snapshot,
            }
        )

        db.add(
            Activity(
                account_id=ctx.import_record.account_id,
                import_id=ctx.import_record.id,
                invoice_id=invoice.id,
                customer_id=invoice.customer_id,
                action_type="invoice_updated",
                details={"changes": planned_invoice.changes},
                performed_by="system",
            )
        )

    for planned_invoice in plan.unchanged_invoices:
        invoice = ctx.orm_invoices_by_id.get(planned_invoice.invoice_id)
        if invoice is None:
            continue
        invoice.days_overdue = max(0, (today - invoice.due_date).days)
        invoice.last_updated_import_id = ctx.import_record.id
        if invoice.first_overdue_at is None and invoice.days_overdue > 0:
            invoice.first_overdue_at = invoice.due_date

    for planned_invoice in plan.disappeared_invoices:
        invoice = ctx.orm_invoices_by_id.get(planned_invoice.invoice_id)
        if invoice is None:
            raise ValueError(
                f"Planned disappeared invoice '{planned_invoice.invoice_id}' no longer exists"
            )

        before_snapshot = {
            "invoice_number": invoice.invoice_number,
            "outstanding_amount": float(invoice.outstanding_amount),
            "gross_amount": float(invoice.gross_amount),
            "due_date": invoice.due_date.isoformat(),
            "customer_id": str(invoice.customer_id),
            "status": invoice.status,
        }

        invoice.status = "possibly_paid"
        invoice.last_updated_import_id = ctx.import_record.id

        change_set["disappeared"].append(
            {
                "invoice_id": str(invoice.id),
                "before": before_snapshot,
            }
        )

        db.add(
            Activity(
                account_id=ctx.import_record.account_id,
                import_id=ctx.import_record.id,
                invoice_id=invoice.id,
                customer_id=invoice.customer_id,
                action_type="invoice_disappeared",
                details={
                    "invoice_number": invoice.invoice_number,
                    "previous_status": before_snapshot["status"],
                    "outstanding_amount": before_snapshot["outstanding_amount"],
                },
                performed_by="system",
            )
        )

    affected_customer_ids: set[uuid.UUID] = set()
    for customer_ref in plan.resolved_customer_refs:
        affected_customer_ids.add(resolve_customer_ref(customer_ref))
    for planned_invoice in plan.disappeared_invoices:
        invoice = ctx.orm_invoices_by_id.get(planned_invoice.invoice_id)
        if invoice is not None and invoice.customer_id is not None:
            affected_customer_ids.add(invoice.customer_id)
    for customer_id in plan.reassigned_old_customer_ids:
        affected_customer_ids.add(uuid.UUID(customer_id))

    for customer_id in affected_customer_ids:
        invoice_query = select(Invoice).where(
            Invoice.account_id == ctx.import_record.account_id,
            Invoice.customer_id == customer_id,
            Invoice.deleted_at.is_(None),
            Invoice.status.not_in(["recovered", "closed"]),
        )
        invoice_result = await db.execute(invoice_query)
        customer_invoices = invoice_result.scalars().all()

        customer = ctx.orm_customers_by_id.get(str(customer_id))
        if customer is None:
            customer = await db.get(Customer, customer_id)
            if customer is not None:
                ctx.orm_customers_by_id[str(customer_id)] = customer

        if customer is not None:
            customer.total_outstanding = sum(
                float(invoice.outstanding_amount) for invoice in customer_invoices
            )
            customer.invoice_count = len(customer_invoices)
            effective_dates = [
                invoice.issue_date or invoice.due_date
                for invoice in customer_invoices
                if invoice.due_date is not None
            ]
            customer.last_invoice_date = max(effective_dates) if effective_dates else None

    for anomaly in plan.anomalies:
        if anomaly.customer_id and anomaly.customer_id.startswith("planned-new-"):
            resolved_customer_id = placeholder_to_real_customer_ids.get(anomaly.customer_id)
            if resolved_customer_id is not None:
                anomaly.customer_id = str(resolved_customer_id)

    for anomaly in plan.anomalies:
        db.add(
            Activity(
                account_id=ctx.import_record.account_id,
                import_id=ctx.import_record.id,
                invoice_id=uuid.UUID(anomaly.invoice_id) if anomaly.invoice_id else None,
                customer_id=uuid.UUID(anomaly.customer_id) if anomaly.customer_id else None,
                action_type="anomaly_flagged",
                details={
                    "anomaly_type": anomaly.anomaly_type,
                    **anomaly.details,
                },
                performed_by="system",
            )
        )
        change_set["anomalies"].append(anomaly_to_dict(anomaly))

    ctx.import_record.status = "confirmed"
    ctx.import_record.invoices_created = len(plan.created_invoices)
    ctx.import_record.invoices_updated = len(plan.updated_invoices)
    ctx.import_record.invoices_disappeared = len(plan.disappeared_invoices)
    ctx.import_record.invoices_unchanged = plan.invoices_unchanged
    ctx.import_record.scope_type = scope_type
    ctx.import_record.skipped_rows = plan.skipped_rows
    ctx.import_record.warnings_text = json.dumps(plan.warnings, ensure_ascii=False)
    ctx.import_record.change_set = change_set
    ctx.import_record.confirmed_at = datetime.now(timezone.utc)

    db.add(
        Activity(
            account_id=ctx.import_record.account_id,
            import_id=ctx.import_record.id,
            action_type="import_committed",
            details={
                "method": ctx.import_record.method,
                "filename": ctx.import_record.original_filename,
                "scope_type": scope_type,
                "invoices_created": len(plan.created_invoices),
                "invoices_updated": len(plan.updated_invoices),
                "invoices_disappeared": len(plan.disappeared_invoices),
                "invoices_unchanged": plan.invoices_unchanged,
                "customers_created": len(plan.new_customers),
                "customers_reused": plan.customers_reused,
                "customers_merged": len(plan.customer_merges),
                "skipped_rows": plan.skipped_rows,
                "anomalies_flagged": len(plan.anomalies),
            },
            performed_by="system",
        )
    )

    import_timestamp = datetime.now(timezone.utc)
    if ctx.account.first_import_at is None:
        ctx.account.first_import_at = import_timestamp
    ctx.account.last_import_at = import_timestamp

    await db.commit()


def _backfill_customer_contact_fields(
    customer: Customer,
    *,
    vat_id: str | None,
    company_id: str | None,
    email: str | None,
    phone: str | None,
) -> None:
    """Backfill blank customer contact fields from import-source data."""

    if not customer.vat_id and vat_id:
        customer.vat_id = vat_id
    if not customer.company_id and company_id:
        customer.company_id = company_id
    if not customer.email and email:
        customer.email = email
    if not customer.phone and phone:
        customer.phone = phone


async def _compute_fuzzy_preview(
    db: AsyncSession,
    account_id: uuid.UUID,
    ingestion_result: Any,
) -> dict[str, Any] | None:
    """Extract unique customer names from parsed data and run fuzzy matching."""

    if ingestion_result.dataframe is None or ingestion_result.mapping is None:
        return None

    customer_name_column: str | None = None
    vat_id_column: str | None = None
    for mapping in ingestion_result.mapping.mappings:
        if mapping.get("target_field") == "customer_name":
            customer_name_column = mapping.get("source_column")
        elif mapping.get("target_field") == "vat_id":
            vat_id_column = mapping.get("source_column")

    if (
        customer_name_column is None
        or customer_name_column not in ingestion_result.dataframe.columns
    ):
        return None

    seen_normalized: set[str] = set()
    file_customers: list[FileCustomer] = []
    for _, row in ingestion_result.dataframe.iterrows():
        raw_name = row.get(customer_name_column)
        if raw_name is None or pd.isna(raw_name) or str(raw_name).strip() == "":
            continue

        normalized_name = normalize_customer_name(str(raw_name))
        if not normalized_name or normalized_name in seen_normalized:
            continue

        seen_normalized.add(normalized_name)

        raw_vat_id: str | None = None
        if vat_id_column and vat_id_column in ingestion_result.dataframe.columns:
            vat_value = row.get(vat_id_column)
            if vat_value is not None and not pd.isna(vat_value) and str(vat_value).strip():
                raw_vat_id = str(vat_value).strip()

        file_customers.append(
            FileCustomer(
                normalized_name=normalized_name,
                raw_name=str(raw_name).strip(),
                vat_id=raw_vat_id,
            )
        )

    if not file_customers:
        return None

    existing_query = select(Customer).where(
        Customer.account_id == account_id,
        Customer.deleted_at.is_(None),
    )
    existing_result = await db.execute(existing_query)
    existing_customers = existing_result.scalars().all()

    if not existing_customers:
        return None

    existing_infos = [
        ExistingCustomerInfo(
            customer_id=str(customer.id),
            normalized_name=customer.normalized_name,
            display_name=customer.name,
            vat_id=customer.vat_id,
            merge_history=customer.merge_history if isinstance(customer.merge_history, list) else None,
        )
        for customer in existing_customers
    ]

    fuzzy_result = find_fuzzy_matches(file_customers, existing_infos)
    if not fuzzy_result.auto_merges and not fuzzy_result.candidates:
        return None

    return fuzzy_match_result_to_dict(fuzzy_result)


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

    reverse_map = {
        source_column: target_field
        for target_field, source_column in confirmed_mapping.items()
    }
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
