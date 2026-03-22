"""Import commit service — creates pending imports and commits confirmed ones to the database."""

from __future__ import annotations

import json
import shutil
import uuid
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
from app.services.customer_matching import (
    ExistingCustomerInfo,
    FileCustomer,
    find_best_match,
    find_fuzzy_matches,
    fuzzy_match_result_to_dict,
)
from app.services.anomaly_detection import (
    Anomaly,
    anomaly_to_dict,
    detect_customer_anomalies,
    detect_invoice_anomalies,
)
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


async def confirm_import(
    db: AsyncSession,
    import_id: uuid.UUID,
    confirmed_mapping: dict[str, str],
    scope_type: str = "unknown",
    merge_decisions: dict[str, str] | None = None,
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

    # Load all existing non-deleted invoices for this account, indexed by normalized_invoice_number
    existing_invoices_query = select(Invoice).where(
        Invoice.account_id == import_record.account_id,
        Invoice.deleted_at.is_(None),
    )
    existing_invoices_result = await db.execute(existing_invoices_query)
    existing_invoices_list = existing_invoices_result.scalars().all()

    # Build lookup: normalized_invoice_number -> Invoice
    # If duplicates exist in DB, the row cannot be safely matched — skip with warning
    existing_invoice_map: dict[str, Invoice] = {}
    ambiguous_normalized_numbers: set[str] = set()
    for inv in existing_invoices_list:
        if inv.normalized_invoice_number in existing_invoice_map:
            ambiguous_normalized_numbers.add(inv.normalized_invoice_number)
        else:
            existing_invoice_map[inv.normalized_invoice_number] = inv

    # Remove ambiguous entries so they are skipped during matching, not silently matched
    for norm_num in ambiguous_normalized_numbers:
        existing_invoice_map.pop(norm_num, None)

    # Pre-scan incoming file for duplicate normalized invoice numbers
    incoming_normalized: dict[str, int] = {}
    incoming_duplicates: set[str] = set()
    for row_index, row in enumerate(canonical_rows, start=1):
        raw_inv = row.get("invoice_number")
        if raw_inv is None or str(raw_inv).strip() == "":
            continue
        norm = normalize_invoice_number(str(raw_inv))
        if norm in incoming_normalized:
            incoming_duplicates.add(norm)
        else:
            incoming_normalized[norm] = row_index

    existing_customers_query = select(Customer).where(
        Customer.account_id == import_record.account_id,
        Customer.deleted_at.is_(None),
    )
    existing_customers_result = await db.execute(existing_customers_query)
    existing_customers_list = existing_customers_result.scalars().all()

    existing_customer_by_normalized: dict[str, Customer] = {}
    existing_customer_by_id: dict[str, Customer] = {}
    for customer in existing_customers_list:
        existing_customer_by_normalized[customer.normalized_name] = customer
        existing_customer_by_id[str(customer.id)] = customer

    merge_history_index: dict[str, Customer] = {}
    for customer in existing_customers_list:
        if isinstance(customer.merge_history, list):
            for entry in customer.merge_history:
                normalized_variant = entry.get("normalized_name")
                if normalized_variant:
                    merge_history_index[normalized_variant] = customer

    existing_customer_infos: list[ExistingCustomerInfo] = []
    existing_customer_info_by_id: dict[str, ExistingCustomerInfo] = {}
    for customer in existing_customers_list:
        info = ExistingCustomerInfo(
            customer_id=str(customer.id),
            normalized_name=customer.normalized_name,
            display_name=customer.name,
            vat_id=customer.vat_id,
            merge_history=customer.merge_history if isinstance(customer.merge_history, list) else None,
        )
        existing_customer_infos.append(info)
        existing_customer_info_by_id[str(customer.id)] = info

    resolved_merges: dict[str, Customer] = {}
    if merge_decisions:
        for normalized_name, customer_id in merge_decisions.items():
            target_customer = existing_customer_by_id.get(customer_id)
            if target_customer is None:
                raise ValueError(
                    f"merge_decisions references unknown customer ID '{customer_id}' "
                    f"for name '{normalized_name}'. Customer must exist and belong to this account."
                )
            resolved_merges[normalized_name] = target_customer

    # Track which existing invoices appear in this import file
    seen_invoice_numbers: set[str] = set()

    # Track old customer IDs when invoices are reassigned to a different customer
    reassigned_old_customer_ids: set[uuid.UUID] = set()

    warnings: list[str] = []
    invoices_created = 0
    invoices_updated = 0
    invoices_disappeared = 0
    invoices_unchanged = 0
    customers_created = 0
    customers_reused = 0
    customers_merged = 0
    errors = 0

    change_set: dict[str, list[dict[str, Any]]] = {
        "created": [],
        "updated": [],
        "disappeared": [],
        "customers_created": [],
        "customers_merged": [],
        "anomalies": [],
    }

    all_anomalies: list[Anomaly] = []
    newly_created_customer_ids: set[uuid.UUID] = set()

    today = date.today()
    customer_cache: dict[str, Customer] = {}

    # Pre-import overdue snapshot for customer-level anomaly detection
    pre_import_overdue_counts: dict[uuid.UUID, int] = {}
    for cust in existing_customers_list:
        count = 0
        for inv in existing_invoices_list:
            if (
                inv.customer_id == cust.id
                and inv.status == "open"
                and inv.due_date is not None
                and inv.due_date < today
            ):
                count += 1
        pre_import_overdue_counts[cust.id] = count

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

        normalized_invoice_number = normalize_invoice_number(str(raw_invoice_number))

        # Skip rows with ambiguous DB matches
        if normalized_invoice_number in ambiguous_normalized_numbers:
            warnings.append(
                f"Row {row_index}: invoice number '{raw_invoice_number}' matches multiple "
                f"existing invoices (ambiguous), skipped"
            )
            errors += 1
            continue

        # Skip duplicate invoice numbers within this file (keep first occurrence)
        if (
            normalized_invoice_number in incoming_duplicates
            and normalized_invoice_number in seen_invoice_numbers
        ):
            warnings.append(
                f"Row {row_index}: duplicate invoice number '{raw_invoice_number}' in file, skipped"
            )
            errors += 1
            continue

        seen_invoice_numbers.add(normalized_invoice_number)

        customer = customer_cache.get(normalized_name)

        if customer is None:
            customer = existing_customer_by_normalized.get(normalized_name)

        is_new_merge = False
        merge_match_type: str | None = None

        if customer is None:
            history_match = merge_history_index.get(normalized_name)
            if history_match is not None:
                customer = history_match

        if customer is None:
            file_customer = FileCustomer(
                normalized_name=normalized_name,
                raw_name=str(raw_customer_name).strip(),
                vat_id=_clean_optional(row.get("vat_id")),
            )
            match = find_best_match(file_customer, existing_customer_infos)

            if match is not None:
                if match.confidence == "high":
                    target = existing_customer_by_id.get(match.existing_customer_id)
                    if target is not None:
                        customer = target
                        is_new_merge = True
                        merge_match_type = match.match_type
                elif match.confidence == "medium":
                    decision_match = resolved_merges.get(normalized_name)
                    if decision_match is not None:
                        customer = decision_match
                        is_new_merge = True
                        merge_match_type = "user_confirmed"

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
            newly_created_customer_ids.add(customer.id)
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

            existing_customer_by_normalized[normalized_name] = customer
            existing_customer_by_id[str(customer.id)] = customer
            new_info = ExistingCustomerInfo(
                customer_id=str(customer.id),
                normalized_name=customer.normalized_name,
                display_name=customer.name,
                vat_id=customer.vat_id,
                merge_history=None,
            )
            existing_customer_infos.append(new_info)
            existing_customer_info_by_id[str(customer.id)] = new_info
            existing_customers_list.append(customer)
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

            info = existing_customer_info_by_id.get(str(customer.id))
            if info is not None:
                info.vat_id = customer.vat_id

        if is_new_merge and normalized_name not in customer_cache:
            customers_merged += 1

            existing_history = customer.merge_history if isinstance(customer.merge_history, list) else []
            customer.merge_history = existing_history + [
                {
                    "variant": str(raw_customer_name).strip(),
                    "normalized_name": normalized_name,
                    "merged_at": datetime.now(timezone.utc).isoformat(),
                    "match_type": merge_match_type,
                }
            ]

            change_set["customers_merged"].append(
                {
                    "customer_id": str(customer.id),
                    "variant": str(raw_customer_name).strip(),
                    "merged_into": customer.name,
                    "match_type": merge_match_type,
                }
            )

            merge_activity = Activity(
                account_id=import_record.account_id,
                import_id=import_record.id,
                customer_id=customer.id,
                action_type="customer_merged",
                details={
                    "merged_variant": str(raw_customer_name).strip(),
                    "merged_into_customer": str(customer.id),
                    "merged_into_name": customer.name,
                    "match_type": merge_match_type,
                },
                performed_by="system",
            )
            db.add(merge_activity)

            merge_history_index[normalized_name] = customer

            info = existing_customer_info_by_id.get(str(customer.id))
            if info is not None:
                info.merge_history = (
                    customer.merge_history if isinstance(customer.merge_history, list) else None
                )

        customer_cache[normalized_name] = customer

        issue_date = _parse_date(row.get("issue_date"))
        currency = _clean_optional(row.get("currency"))
        currency = (currency or account_currency).upper()

        days_overdue = max(0, (today - due_date).days)

        # --- DIFF: check if this invoice already exists ---
        existing_invoice = existing_invoice_map.get(normalized_invoice_number)

        if existing_invoice is not None:
            # Compare fields to determine updated vs unchanged
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
            # Customer reassignment
            if existing_invoice.customer_id != customer.id:
                changes["customer_id"] = {
                    "before": str(existing_invoice.customer_id),
                    "after": str(customer.id),
                }
                # Track old customer so its aggregates get recalculated
                if existing_invoice.customer_id is not None:
                    reassigned_old_customer_ids.add(existing_invoice.customer_id)

            # Reappearance: invoice was possibly_paid but is back in the file -> always an update
            if existing_invoice.status == "possibly_paid":
                changes["status"] = {
                    "before": "possibly_paid",
                    "after": "open",
                }

            # --- ANOMALY DETECTION (invoice-level) ---
            invoice_anomalies = detect_invoice_anomalies(
                invoice_id=str(existing_invoice.id),
                customer_id=str(customer.id),
                invoice_number=existing_invoice.invoice_number,
                existing_status=existing_invoice.status,
                existing_outstanding=float(existing_invoice.outstanding_amount),
                new_outstanding=float(outstanding_amount),
                existing_due_date=existing_invoice.due_date,
                new_due_date=due_date,
            )
            all_anomalies.extend(invoice_anomalies)

            if changes:
                # --- UPDATED ---
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

                # Apply updates to mutable fields (raw invoice_number is immutable — not updated)
                existing_invoice.outstanding_amount = outstanding_amount
                existing_invoice.gross_amount = gross_amount
                existing_invoice.due_date = due_date
                existing_invoice.issue_date = issue_date
                existing_invoice.currency = currency
                existing_invoice.customer_id = customer.id
                existing_invoice.days_overdue = days_overdue
                existing_invoice.last_updated_import_id = import_record.id

                # Preserve first_overdue_at if already set; set it if newly overdue
                if existing_invoice.first_overdue_at is None and days_overdue > 0:
                    existing_invoice.first_overdue_at = due_date

                # Restore status if reappearing
                if existing_invoice.status == "possibly_paid":
                    existing_invoice.status = "open"

                after_snapshot = {
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

                invoices_updated += 1
                change_set["updated"].append(
                    {
                        "invoice_id": str(existing_invoice.id),
                        "before": before_snapshot,
                        "after": after_snapshot,
                    }
                )

                # Activity for update
                update_activity = Activity(
                    account_id=import_record.account_id,
                    import_id=import_record.id,
                    invoice_id=existing_invoice.id,
                    customer_id=customer.id,
                    action_type="invoice_updated",
                    details={"changes": changes},
                    performed_by="system",
                )
                db.add(update_activity)
            else:
                # --- UNCHANGED ---
                # Refresh days_overdue (date-relative) and last_updated_import_id
                existing_invoice.days_overdue = days_overdue
                existing_invoice.last_updated_import_id = import_record.id
                # Set first_overdue_at if the invoice has become overdue since first import
                if existing_invoice.first_overdue_at is None and days_overdue > 0:
                    existing_invoice.first_overdue_at = due_date
                invoices_unchanged += 1
        else:
            # --- NEW INVOICE ---
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

        effective_invoice_date = issue_date or due_date
        if customer.last_invoice_date is None or effective_invoice_date > customer.last_invoice_date:
            customer.last_invoice_date = effective_invoice_date

    # --- DISAPPEARANCE DETECTION (only for full_snapshot imports) ---
    if scope_type == "full_snapshot":
        active_statuses = {"open", "promised", "disputed", "paused", "escalated"}

        for norm_num, existing_inv in existing_invoice_map.items():
            if norm_num in seen_invoice_numbers:
                continue
            if existing_inv.status not in active_statuses:
                continue

            before_snapshot = {
                "invoice_number": existing_inv.invoice_number,
                "outstanding_amount": float(existing_inv.outstanding_amount),
                "gross_amount": float(existing_inv.gross_amount),
                "due_date": existing_inv.due_date.isoformat(),
                "customer_id": str(existing_inv.customer_id),
                "status": existing_inv.status,
            }

            existing_inv.status = "possibly_paid"
            existing_inv.last_updated_import_id = import_record.id

            invoices_disappeared += 1
            change_set["disappeared"].append(
                {
                    "invoice_id": str(existing_inv.id),
                    "before": before_snapshot,
                }
            )

            disappear_activity = Activity(
                account_id=import_record.account_id,
                import_id=import_record.id,
                invoice_id=existing_inv.id,
                customer_id=existing_inv.customer_id,
                action_type="invoice_disappeared",
                details={
                    "invoice_number": existing_inv.invoice_number,
                    "previous_status": before_snapshot["status"],
                    "outstanding_amount": before_snapshot["outstanding_amount"],
                },
                performed_by="system",
            )
            db.add(disappear_activity)

    if (invoices_created + invoices_updated + invoices_unchanged) == 0:
        raise ValueError("No valid rows to import")

    # Recalculate customer aggregates for all affected customers
    affected_customer_ids: set[uuid.UUID] = set()
    for customer in customer_cache.values():
        affected_customer_ids.add(customer.id)
    # Include customers of disappeared invoices
    for item in change_set["disappeared"]:
        cid_str = item["before"].get("customer_id")
        if cid_str:
            affected_customer_ids.add(uuid.UUID(cid_str))
    # Include previous customers of reassigned invoices (their totals are now stale)
    affected_customer_ids.update(reassigned_old_customer_ids)

    for cid in affected_customer_ids:
        # Count all non-deleted, non-recovered, non-closed invoices
        inv_query = select(Invoice).where(
            Invoice.account_id == import_record.account_id,
            Invoice.customer_id == cid,
            Invoice.deleted_at.is_(None),
            Invoice.status.not_in(["recovered", "closed"]),
        )
        inv_result = await db.execute(inv_query)
        customer_invoices = inv_result.scalars().all()

        # Find the customer object
        cust = None
        for cached_cust in customer_cache.values():
            if cached_cust.id == cid:
                cust = cached_cust
                break
        if cust is None:
            cust = await db.get(Customer, cid)

        if cust is not None:
            cust.total_outstanding = sum(float(i.outstanding_amount) for i in customer_invoices)
            cust.invoice_count = len(customer_invoices)

    # --- CUSTOMER-LEVEL ANOMALY DETECTION ---
    for cid in affected_customer_ids:
        # Count post-import overdue invoices (status='open' and past due)
        post_overdue_query = select(func.count()).select_from(Invoice).where(
            Invoice.account_id == import_record.account_id,
            Invoice.customer_id == cid,
            Invoice.deleted_at.is_(None),
            Invoice.status == "open",
            Invoice.due_date < today,
        )
        post_overdue_result = await db.execute(post_overdue_query)
        post_overdue_count = post_overdue_result.scalar() or 0

        pre_overdue_count = pre_import_overdue_counts.get(cid, 0)

        # Look up customer name for anomaly details
        cust_name = None
        for cached_cust in customer_cache.values():
            if cached_cust.id == cid:
                cust_name = cached_cust.name
                break
        if cust_name is None:
            cust_obj = await db.get(Customer, cid)
            cust_name = cust_obj.name if cust_obj else "Unknown"

        customer_anomalies = detect_customer_anomalies(
            customer_id=str(cid),
            customer_name=cust_name,
            pre_overdue_count=pre_overdue_count,
            post_overdue_count=post_overdue_count,
            is_new_customer=cid in newly_created_customer_ids,
        )
        all_anomalies.extend(customer_anomalies)

    # --- ANOMALY ACTIVITY RECORDS ---
    for anomaly in all_anomalies:
        anomaly_activity = Activity(
            account_id=import_record.account_id,
            import_id=import_record.id,
            invoice_id=uuid.UUID(anomaly.invoice_id) if anomaly.invoice_id else None,
            customer_id=uuid.UUID(anomaly.customer_id) if anomaly.customer_id else None,
            action_type="anomaly_flagged",
            details={
                "anomaly_type": anomaly.anomaly_type,
                **anomaly.details,
            },
            performed_by="system",
        )
        db.add(anomaly_activity)
        change_set["anomalies"].append(anomaly_to_dict(anomaly))

    import_record.status = "confirmed"
    import_record.invoices_created = invoices_created
    import_record.invoices_updated = invoices_updated
    import_record.invoices_disappeared = invoices_disappeared
    import_record.invoices_unchanged = invoices_unchanged
    import_record.scope_type = scope_type
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
            "scope_type": scope_type,
            "invoices_created": invoices_created,
            "invoices_updated": invoices_updated,
            "invoices_disappeared": invoices_disappeared,
            "invoices_unchanged": invoices_unchanged,
            "customers_created": customers_created,
            "customers_reused": customers_reused,
            "customers_merged": customers_merged,
            "errors": errors,
            "anomalies_flagged": len(all_anomalies),
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
        "scope_type": scope_type,
        "invoices_created": invoices_created,
        "invoices_updated": invoices_updated,
        "invoices_disappeared": invoices_disappeared,
        "invoices_unchanged": invoices_unchanged,
        "customers_created": customers_created,
        "customers_reused": customers_reused,
        "customers_merged": customers_merged,
        "errors": errors,
        "warnings": warnings,
        "anomalies_flagged": len(all_anomalies),
        "anomalies": [anomaly_to_dict(a) for a in all_anomalies],
    }


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
