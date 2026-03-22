from __future__ import annotations

import json
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.models.account import Account
from app.models.activity import Activity
from app.models.customer import Customer
from app.models.import_record import ImportRecord
from app.models.invoice import Invoice
from app.services.import_commit import confirm_import, create_pending_import
from app.services.ingestion import ingest_file as base_ingest_file
from app.services.normalization import normalize_customer_name, normalize_invoice_number

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _read_fixture(filename: str) -> bytes:
    return (SAMPLE_DIR / filename).read_bytes()


def _mapping_from_preview(preview: dict) -> dict[str, str]:
    assert preview["mapping"] is not None
    return {
        mapping["target_field"]: mapping["source_column"]
        for mapping in preview["mapping"]["mappings"]
    }


async def _create_pending_from_bytes(
    db_session,
    account_id: uuid.UUID,
    *,
    file_bytes: bytes,
    filename: str,
) -> tuple[uuid.UUID, dict[str, str], dict]:
    result = await create_pending_import(
        db=db_session,
        account_id=account_id,
        file_bytes=file_bytes,
        filename=filename,
    )
    assert result["import_id"] is not None
    return result["import_id"], _mapping_from_preview(result["preview"]), result


async def _create_and_get_pending(db_session, test_account, fixture: str = "french_ar_export.csv"):
    return await _create_pending_from_bytes(
        db_session,
        test_account.id,
        file_bytes=_read_fixture(fixture),
        filename=fixture,
    )


def _build_csv(headers: list[str], rows: list[list[str]]) -> bytes:
    lines = [",".join(headers), *(",".join(row) for row in rows)]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _build_two_invoice_csv(
    invoices: list[list[str]],
) -> bytes:
    """Build a CSV with the standard 5-column header and given invoice rows."""
    return _build_csv(
        ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
        invoices,
    )


class TestCreatePendingImport:
    @pytest.mark.asyncio
    async def test_creates_pending_import_record(self, db_session, test_account):
        import_id, mapping, result = await _create_and_get_pending(
            db_session, test_account, "french_ar_export.csv"
        )

        record = await db_session.get(ImportRecord, import_id)
        assert record is not None
        assert record.status == "pending_preview"
        assert record.rows_found == result["preview"]["total_rows"]
        assert record.file_hash == result["preview"]["file_hash"]
        assert record.original_filename == "french_ar_export.csv"
        assert "invoice_number" in mapping

    @pytest.mark.asyncio
    async def test_pending_import_created_even_with_imperfect_mapping(self, db_session, test_account):
        async def fake_ingest_file(file_bytes: bytes, filename: str, method: str = "upload"):
            result = await base_ingest_file(
                file_bytes,
                filename,
                method=method,
            )
            result.success = False
            if result.mapping is not None:
                result.mapping.success = False
            return result

        with patch("app.services.import_commit.ingest_file", new=fake_ingest_file):
            result = await create_pending_import(
                db=db_session,
                account_id=test_account.id,
                file_bytes=_read_fixture("pohoda_ar_export.csv"),
                filename="pohoda_ar_export.csv",
            )

        assert result["import_id"] is not None
        assert result["preview"]["success"] is False
        assert result["preview"]["mapping"]["success"] is False
        record = await db_session.get(ImportRecord, result["import_id"])
        assert record is not None
        assert record.status == "pending_preview"

    @pytest.mark.asyncio
    async def test_duplicate_warning_on_same_hash(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(
            db_session, test_account, "french_ar_export.csv"
        )
        await confirm_import(db_session, import_id, mapping)

        second = await create_pending_import(
            db=db_session,
            account_id=test_account.id,
            file_bytes=_read_fixture("french_ar_export.csv"),
            filename="french_ar_export.csv",
        )

        assert second["import_id"] is not None
        assert second["duplicate_warning"] is not None
        assert "identical" in second["duplicate_warning"].lower()

    @pytest.mark.asyncio
    async def test_file_saved_to_disk(self, db_session, test_account):
        file_bytes = _read_fixture("italian_ar_export.csv")
        import_id, _, _ = await _create_pending_from_bytes(
            db_session,
            test_account.id,
            file_bytes=file_bytes,
            filename="italian_ar_export.csv",
        )

        record = await db_session.get(ImportRecord, import_id)
        assert record is not None
        assert record.original_file_path is not None
        stored_path = Path(record.original_file_path)
        assert stored_path.exists()
        assert stored_path.read_bytes() == file_bytes

    @pytest.mark.asyncio
    async def test_parse_failure_returns_no_import_id(self, db_session, test_account):
        result = await create_pending_import(
            db=db_session,
            account_id=test_account.id,
            file_bytes=b"",
            filename="empty.csv",
        )

        count = await db_session.scalar(select(func.count()).select_from(ImportRecord))
        assert result["import_id"] is None
        assert result["preview"]["success"] is False
        assert count == 0


class TestConfirmImport:
    @pytest.mark.asyncio
    async def test_confirm_creates_invoices(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        summary = await confirm_import(db_session, import_id, mapping)

        invoices = (
            await db_session.execute(
                select(Invoice).where(Invoice.account_id == test_account.id)
            )
        ).scalars().all()

        assert summary["invoices_created"] > 0
        assert len(invoices) == summary["invoices_created"]

    @pytest.mark.asyncio
    async def test_confirm_creates_customers(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(
            db_session, test_account, "italian_ar_export.csv"
        )
        await confirm_import(db_session, import_id, mapping)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()
        assert len(customers) > 0

    @pytest.mark.asyncio
    async def test_confirm_deduplicates_customers_within_import(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(
            db_session, test_account, "french_ar_export.csv"
        )
        summary = await confirm_import(db_session, import_id, mapping)

        customer_count = await db_session.scalar(
            select(func.count()).select_from(Customer).where(Customer.account_id == test_account.id)
        )
        assert summary["invoices_created"] == 12
        assert customer_count < summary["invoices_created"]

    @pytest.mark.asyncio
    async def test_confirm_sets_import_record_status(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        summary = await confirm_import(db_session, import_id, mapping)

        record = await db_session.get(ImportRecord, import_id)
        assert record is not None
        assert record.status == "confirmed"
        assert record.confirmed_at is not None
        assert record.invoices_created == summary["invoices_created"]
        assert record.invoices_updated == 0
        assert record.invoices_disappeared == 0
        assert record.invoices_unchanged == 0
        assert record.change_set is not None
        assert record.change_set["created"]

    @pytest.mark.asyncio
    async def test_confirm_populates_errors_and_warnings_text(self, db_session, test_account):
        csv_bytes = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [
                ["INV-1", "Valid Company Ltd.", "2026-01-20", "100.00", "100.00"],
                ["INV-2", "Broken Company Ltd.", "", "50.00", "50.00"],
            ],
        )
        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session,
            test_account.id,
            file_bytes=csv_bytes,
            filename="warnings.csv",
        )

        summary = await confirm_import(db_session, import_id, mapping)
        record = await db_session.get(ImportRecord, import_id)
        warnings = json.loads(record.warnings_text or "[]")

        assert summary["errors"] == 1
        assert record.errors == 1
        assert isinstance(warnings, list)
        assert any("due_date" in warning for warning in warnings)

    @pytest.mark.asyncio
    async def test_confirm_creates_activity(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        await confirm_import(db_session, import_id, mapping)

        activity = await db_session.scalar(
            select(Activity).where(
                Activity.import_id == import_id,
                Activity.action_type == "import_committed",
            )
        )
        assert activity is not None

    @pytest.mark.asyncio
    async def test_confirm_updates_account_timestamps(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        await confirm_import(db_session, import_id, mapping)

        account = await db_session.get(Account, test_account.id)
        assert account is not None
        assert account.first_import_at is not None
        assert account.last_import_at is not None

    @pytest.mark.asyncio
    async def test_confirm_computes_days_overdue(self, db_session, test_account):
        today = date.today()
        csv_bytes = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [
                ["INV-OD-1", "Overdue Co Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"],
                ["INV-OD-2", "Future Co Ltd.", (today + timedelta(days=5)).isoformat(), "50.00", "50.00"],
            ],
        )
        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session,
            test_account.id,
            file_bytes=csv_bytes,
            filename="days_overdue.csv",
        )
        await confirm_import(db_session, import_id, mapping)

        invoices = (
            await db_session.execute(
                select(Invoice).where(Invoice.account_id == test_account.id).order_by(Invoice.invoice_number)
            )
        ).scalars().all()

        assert any(invoice.days_overdue > 0 for invoice in invoices)
        assert any(invoice.first_overdue_at is not None for invoice in invoices if invoice.days_overdue > 0)

    @pytest.mark.asyncio
    async def test_confirm_builds_change_set_for_rollback(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        summary = await confirm_import(db_session, import_id, mapping)

        record = await db_session.get(ImportRecord, import_id)
        assert record is not None
        assert set(record.change_set.keys()) == {
            "created",
            "updated",
            "disappeared",
            "customers_created",
            "customers_merged",
        }
        assert len(record.change_set["created"]) == summary["invoices_created"]
        assert record.change_set["updated"] == []
        assert record.change_set["disappeared"] == []
        assert record.change_set["customers_merged"] == []
        assert all("invoice_id" in item and "data" in item for item in record.change_set["created"])

    @pytest.mark.asyncio
    async def test_confirm_already_confirmed_raises(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        await confirm_import(db_session, import_id, mapping)

        with pytest.raises(ValueError, match="expected 'pending_preview'"):
            await confirm_import(db_session, import_id, mapping)

    @pytest.mark.asyncio
    async def test_confirm_nonexistent_import_raises(self, db_session):
        with pytest.raises(ValueError, match="not found"):
            await confirm_import(db_session, uuid.uuid4(), {})

    @pytest.mark.asyncio
    async def test_customer_reused_across_rows(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(
            db_session, test_account, "pohoda_ar_export.csv"
        )
        summary = await confirm_import(db_session, import_id, mapping)

        assert summary["customers_created"] + summary["customers_reused"] >= summary["invoices_created"]
        assert summary["customers_reused"] > 0

    @pytest.mark.asyncio
    async def test_invoice_normalized_number_stored(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(
            db_session, test_account, "italian_ar_export.csv"
        )
        await confirm_import(db_session, import_id, mapping)

        invoice = await db_session.scalar(
            select(Invoice).where(Invoice.account_id == test_account.id).order_by(Invoice.invoice_number)
        )
        assert invoice is not None
        assert invoice.invoice_number != invoice.normalized_invoice_number
        assert invoice.normalized_invoice_number == normalize_invoice_number(invoice.invoice_number)

    @pytest.mark.asyncio
    async def test_skipped_row_does_not_create_orphan_customer(self, db_session, test_account):
        csv_bytes = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [
                ["INV-ORPHAN-1", "Orphan Customer Ltd.", "", "100.00", "100.00"],
                ["INV-VALID-1", "Valid Customer Ltd.", "2026-01-20", "80.00", "80.00"],
            ],
        )
        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session,
            test_account.id,
            file_bytes=csv_bytes,
            filename="orphan_guard.csv",
        )
        await confirm_import(db_session, import_id, mapping)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id).order_by(Customer.name)
            )
        ).scalars().all()

        normalized_names = {customer.normalized_name for customer in customers}
        assert normalize_customer_name("Orphan Customer Ltd.") not in normalized_names
        assert normalize_customer_name("Valid Customer Ltd.") in normalized_names
        assert len(customers) == 1

    @pytest.mark.asyncio
    async def test_all_fixtures_commit_successfully(self, db_session, test_account):
        fixtures = [
            "pohoda_ar_export.csv",
            "fakturoid_ar_export.csv",
            "messy_generic_export.csv",
            "french_ar_export.csv",
            "italian_ar_export.csv",
            "german_ar_export.xlsx",
        ]

        for fixture in fixtures:
            import_id, mapping, _ = await _create_and_get_pending(db_session, test_account, fixture)
            summary = await confirm_import(db_session, import_id, mapping)
            assert summary["status"] == "confirmed"
            assert summary["invoices_created"] > 0


class TestMappingValidation:
    @pytest.mark.asyncio
    async def test_invalid_source_column_rejected(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        mapping["invoice_number"] = "Missing Column"

        with pytest.raises(ValueError, match="not in file"):
            await confirm_import(db_session, import_id, mapping)

    @pytest.mark.asyncio
    async def test_missing_required_field_rejected(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        mapping.pop("invoice_number")

        with pytest.raises(ValueError, match="Required fields missing"):
            await confirm_import(db_session, import_id, mapping)


class TestFuzzyMerge:
    """Integration tests for fuzzy customer matching in confirm_import."""

    @pytest.mark.asyncio
    async def test_exact_match_unchanged(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv([["INV-002", "Acme Ltd.", due_str, "50.00", "50.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="exact-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="exact-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_reused"] == 1
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_accent_variant_auto_merge(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Société Générale", due_str, "1000.00", "1000.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="accent-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Societe Generale", due_str, "500.00", "500.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="accent-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_merged"] == 1
        assert summary["customers_created"] == 0

        customer = customers[0]
        assert isinstance(customer.merge_history, list)
        assert len(customer.merge_history) == 1
        assert customer.merge_history[0]["variant"] == "Societe Generale"
        assert customer.merge_history[0]["match_type"] == "name_similarity"

    @pytest.mark.asyncio
    async def test_vat_id_merge(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount", "VAT ID"],
            [["INV-001", "Alpha Corp.", due_str, "100.00", "100.00", "FR12345678901"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="vat-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount", "VAT ID"],
            [["INV-002", "Alpha Corporation France", due_str, "200.00", "200.00", "FR12345678901"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="vat-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_merged"] == 1

    @pytest.mark.asyncio
    async def test_merge_history_reuse_no_duplicate_merge(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()

        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Société Générale", due_str, "1000.00", "1000.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="hist-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Societe Generale", due_str, "500.00", "500.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="hist-2.csv"
        )
        summary2 = await confirm_import(db_session, id2, map2)
        assert summary2["customers_merged"] == 1

        csv3 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-003", "Societe Generale", due_str, "300.00", "300.00"]],
        )
        id3, map3, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv3, filename="hist-3.csv"
        )
        summary3 = await confirm_import(db_session, id3, map3)

        assert summary3["customers_merged"] == 0
        assert summary3["customers_reused"] == 1

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1

        customer = customers[0]
        assert isinstance(customer.merge_history, list)
        assert len(customer.merge_history) == 1

        merge_activities = (
            await db_session.execute(
                select(Activity).where(
                    Activity.account_id == test_account.id,
                    Activity.action_type == "customer_merged",
                )
            )
        ).scalars().all()

        assert len(merge_activities) == 1

    @pytest.mark.asyncio
    async def test_user_confirmed_merge_decision(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Beta Services", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="decision-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        customer = await db_session.scalar(
            select(Customer).where(Customer.account_id == test_account.id)
        )
        assert customer is not None

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Beta Consulting Services", due_str, "200.00", "200.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="decision-2.csv"
        )

        normalized_name = normalize_customer_name("Beta Consulting Services")
        summary = await confirm_import(
            db_session,
            id2,
            map2,
            merge_decisions={normalized_name: str(customer.id)},
        )

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_merged"] == 1

    @pytest.mark.asyncio
    async def test_invalid_merge_decision_rejected(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Some Company", due_str, "100.00", "100.00"]],
        )
        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv, filename="invalid-decision.csv"
        )

        fake_id = str(uuid.uuid4())
        with pytest.raises(ValueError, match="unknown customer ID"):
            await confirm_import(
                db_session,
                import_id,
                mapping,
                merge_decisions={"some company": fake_id},
            )

    @pytest.mark.asyncio
    async def test_no_merge_decision_creates_new(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Gamma Tech", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="nomerge-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Delta Industries", due_str, "200.00", "200.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="nomerge-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 2
        assert summary["customers_created"] == 1
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_medium_confidence_without_merge_decision_creates_new(
        self,
        db_session,
        test_account,
    ):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Beta Services", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="medium-nodecision-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Beta Consulting Services", due_str, "200.00", "200.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="medium-nodecision-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 2
        assert summary["customers_created"] == 1
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_related_but_distinct_not_auto_merged(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Global Corp France", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="related-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Global Corp Germany", due_str, "200.00", "200.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="related-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 2
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_customer_merged_activity_created(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Société Générale", due_str, "1000.00", "1000.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="activity-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Societe Generale", due_str, "500.00", "500.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="activity-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        merge_activities = (
            await db_session.execute(
                select(Activity).where(
                    Activity.account_id == test_account.id,
                    Activity.action_type == "customer_merged",
                )
            )
        ).scalars().all()

        assert len(merge_activities) == 1
        assert merge_activities[0].details["merged_variant"] == "Societe Generale"

    @pytest.mark.asyncio
    async def test_change_set_records_merge(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Société Générale", due_str, "1000.00", "1000.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="cs-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Societe Generale", due_str, "500.00", "500.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="cs-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        import_record = await db_session.get(ImportRecord, id2)
        assert import_record is not None
        assert import_record.change_set is not None
        assert len(import_record.change_set["customers_merged"]) == 1
        assert import_record.change_set["customers_merged"][0]["variant"] == "Societe Generale"

    @pytest.mark.asyncio
    async def test_suffix_variant_exact_match_not_fuzzy(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Acme S.R.L.", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="suffix-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Acme SRL", due_str, "200.00", "200.00"]],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="suffix-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_reused"] == 1
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_fuzzy_preview_returned(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Société Générale", due_str, "1000.00", "1000.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="preview-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-002", "Societe Generale", due_str, "500.00", "500.00"]],
        )
        result = await create_pending_import(
            db=db_session,
            account_id=test_account.id,
            file_bytes=csv2,
            filename="preview-2.csv",
        )

        assert "fuzzy_matches" in result

    @pytest.mark.asyncio
    async def test_confirm_returns_customers_merged_key(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv, filename="compat.csv"
        )
        summary = await confirm_import(db_session, id1, map1)

        assert "customers_merged" in summary
        assert summary["customers_merged"] == 0

    @pytest.mark.asyncio
    async def test_same_import_fuzzy_dedup(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [
                ["INV-001", "Société Générale", due_str, "1000.00", "1000.00"],
                ["INV-002", "Societe Generale", due_str, "500.00", "500.00"],
            ],
        )
        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv, filename="same-import-dedup.csv"
        )
        summary = await confirm_import(db_session, import_id, mapping)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()
        assert len(customers) == 1

        invoices = (
            await db_session.execute(
                select(Invoice).where(Invoice.account_id == test_account.id)
            )
        ).scalars().all()
        assert len(invoices) == 2
        assert invoices[0].customer_id == invoices[1].customer_id

        assert summary["customers_created"] == 1
        assert summary["customers_merged"] == 1

    @pytest.mark.asyncio
    async def test_same_import_vat_backfill_visibility(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()

        csv1 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount"],
            [["INV-001", "Alpha Corp", due_str, "100.00", "100.00"]],
        )
        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="vat-backfill-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        customer = await db_session.scalar(
            select(Customer).where(Customer.account_id == test_account.id)
        )
        assert customer is not None
        assert customer.vat_id is None

        csv2 = _build_csv(
            ["Invoice Number", "Client Name", "Due Date", "Amount Due", "Total Amount", "VAT ID"],
            [
                ["INV-002", "Alpha Corp", due_str, "200.00", "200.00", "FR99999999999"],
                ["INV-003", "Alpha Corporation FR", due_str, "300.00", "300.00", "FR99999999999"],
            ],
        )
        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="vat-backfill-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        customers = (
            await db_session.execute(
                select(Customer).where(Customer.account_id == test_account.id)
            )
        ).scalars().all()

        assert len(customers) == 1
        assert summary["customers_merged"] == 1
        assert summary["customers_created"] == 0

    @pytest.mark.asyncio
    async def test_amount_fallback_accepted(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        mapping.pop("outstanding_amount", None)

        summary = await confirm_import(db_session, import_id, mapping)
        assert summary["invoices_created"] > 0

    @pytest.mark.asyncio
    async def test_no_amount_at_all_rejected(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        mapping.pop("outstanding_amount", None)
        mapping.pop("gross_amount", None)

        with pytest.raises(ValueError, match="Required fields missing"):
            await confirm_import(db_session, import_id, mapping)

    @pytest.mark.asyncio
    async def test_duplicate_source_column_rejected(self, db_session, test_account):
        import_id, mapping, _ = await _create_and_get_pending(db_session, test_account)
        mapping["customer_name"] = mapping["invoice_number"]

        with pytest.raises(ValueError, match="multiple targets"):
            await confirm_import(db_session, import_id, mapping)


class TestDiffEngine:
    @pytest.mark.asyncio
    async def test_second_import_unchanged(self, db_session, test_account):
        today = date.today()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"],
                ["INV-002", "Beta Corp.", (today - timedelta(days=5)).isoformat(), "200.00", "200.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="import1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="import2.csv"
        )
        summary2 = await confirm_import(db_session, id2, map2)

        assert summary2["invoices_created"] == 0
        assert summary2["invoices_updated"] == 0
        assert summary2["invoices_unchanged"] == 2
        assert summary2["invoices_disappeared"] == 0

        record = await db_session.get(ImportRecord, id2)
        assert record is not None
        assert record.invoices_created == 0
        assert record.invoices_updated == 0
        assert record.invoices_unchanged == 2
        assert record.invoices_disappeared == 0
        assert record.change_set["created"] == []
        assert record.change_set["updated"] == []
        assert record.change_set["disappeared"] == []

    @pytest.mark.asyncio
    async def test_second_import_updated_balance(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "75.00", "75.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="balance-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="balance-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        assert summary["invoices_updated"] == 1
        assert summary["invoices_created"] == 0

        record = await db_session.get(ImportRecord, id2)
        assert record is not None
        assert len(record.change_set["updated"]) == 1
        updated = record.change_set["updated"][0]
        assert updated["before"]["outstanding_amount"] == 100.0
        assert updated["after"]["outstanding_amount"] == 75.0

        invoice = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-001"),
            )
        )
        assert invoice is not None
        assert float(invoice.outstanding_amount) == 75.0

        activity = await db_session.scalar(
            select(Activity).where(
                Activity.import_id == id2,
                Activity.action_type == "invoice_updated",
            )
        )
        assert activity is not None

    @pytest.mark.asyncio
    async def test_second_import_disappeared_full_snapshot(self, db_session, test_account):
        today = date.today()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"],
                ["INV-002", "Beta Corp.", (today - timedelta(days=5)).isoformat(), "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv(
            [["INV-001", "Acme Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"]]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="snapshot-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="snapshot-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2, scope_type="full_snapshot")

        assert summary["invoices_disappeared"] == 1
        assert summary["invoices_unchanged"] == 1

        inv_002 = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-002"),
            )
        )
        assert inv_002 is not None
        assert inv_002.status == "possibly_paid"

        record = await db_session.get(ImportRecord, id2)
        assert record is not None
        assert len(record.change_set["disappeared"]) == 1

        activity = await db_session.scalar(
            select(Activity).where(
                Activity.import_id == id2,
                Activity.action_type == "invoice_disappeared",
            )
        )
        assert activity is not None

    @pytest.mark.asyncio
    async def test_no_disappearance_without_full_snapshot(self, db_session, test_account):
        today = date.today()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"],
                ["INV-002", "Beta Corp.", (today - timedelta(days=5)).isoformat(), "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv(
            [["INV-001", "Acme Ltd.", (today - timedelta(days=10)).isoformat(), "100.00", "100.00"]]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="partial-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="partial-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        assert summary["invoices_disappeared"] == 0

        inv_002 = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-002"),
            )
        )
        assert inv_002 is not None
        assert inv_002.status == "open"

    @pytest.mark.asyncio
    async def test_second_import_new_invoice_alongside_existing(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-003", "Gamma GmbH", due_str, "300.00", "300.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="existing-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="existing-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        assert summary["invoices_unchanged"] == 1
        assert summary["invoices_created"] == 1
        assert summary["invoices_disappeared"] == 0

    @pytest.mark.asyncio
    async def test_mixed_diff_scenario(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Beta Corp.", due_str, "200.00", "200.00"],
                ["INV-003", "Gamma GmbH", due_str, "300.00", "300.00"],
            ]
        )
        csv2 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Beta Corp.", due_str, "150.00", "150.00"],
                ["INV-004", "Delta Sarl", due_str, "400.00", "400.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="mixed-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="mixed-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2, scope_type="full_snapshot")

        assert summary["invoices_created"] == 1
        assert summary["invoices_updated"] == 1
        assert summary["invoices_unchanged"] == 1
        assert summary["invoices_disappeared"] == 1

        invoice_count = await db_session.scalar(
            select(func.count()).select_from(Invoice).where(Invoice.account_id == test_account.id)
        )
        assert invoice_count == 4

    @pytest.mark.asyncio
    async def test_disappeared_not_flagged_if_already_recovered(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Beta Corp.", due_str, "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="recovered-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        inv_result = await db_session.execute(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-002"),
            )
        )
        inv_002 = inv_result.scalar_one()
        inv_002.status = "recovered"
        await db_session.commit()

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="recovered-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2, scope_type="full_snapshot")

        assert summary["invoices_disappeared"] == 0

        inv_002 = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-002"),
            )
        )
        assert inv_002 is not None
        assert inv_002.status == "recovered"

    @pytest.mark.asyncio
    async def test_reappeared_invoice_restored_to_open(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv_all = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Beta Corp.", due_str, "200.00", "200.00"],
            ]
        )
        csv_missing = _build_two_invoice_csv(
            [["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv_all, filename="reappear-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv_missing, filename="reappear-2.csv"
        )
        await confirm_import(db_session, id2, map2, scope_type="full_snapshot")

        id3, map3, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv_all, filename="reappear-3.csv"
        )
        summary = await confirm_import(db_session, id3, map3)

        assert summary["invoices_updated"] == 1

        inv_002 = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-002"),
            )
        )
        assert inv_002 is not None
        assert inv_002.status == "open"

    @pytest.mark.asyncio
    async def test_customer_aggregates_recalculated_after_update(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Acme Ltd.", due_str, "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "50.00", "50.00"],
                ["INV-002", "Acme Ltd.", due_str, "200.00", "200.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="aggregate-update-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="aggregate-update-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        customer = await db_session.scalar(
            select(Customer).where(
                Customer.account_id == test_account.id,
                Customer.normalized_name == normalize_customer_name("Acme Ltd."),
            )
        )
        assert customer is not None
        assert float(customer.total_outstanding) == 250.0

    @pytest.mark.asyncio
    async def test_customer_aggregates_include_possibly_paid(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Acme Ltd.", due_str, "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="aggregate-disappear-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="aggregate-disappear-2.csv"
        )
        await confirm_import(db_session, id2, map2, scope_type="full_snapshot")

        customer = await db_session.scalar(
            select(Customer).where(
                Customer.account_id == test_account.id,
                Customer.normalized_name == normalize_customer_name("Acme Ltd."),
            )
        )
        assert customer is not None
        assert float(customer.total_outstanding) == 300.0
        assert customer.invoice_count == 2

    @pytest.mark.asyncio
    async def test_change_set_structure_on_update(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "80.00", "80.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="changes-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="changes-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        record = await db_session.get(ImportRecord, id2)
        assert record is not None
        assert set(record.change_set.keys()) == {
            "created",
            "updated",
            "disappeared",
            "customers_created",
            "customers_merged",
        }
        assert set(record.change_set["updated"][0].keys()) == {"invoice_id", "before", "after"}
        assert record.change_set["updated"][0]["before"]["outstanding_amount"] == 100.0
        assert record.change_set["updated"][0]["after"]["outstanding_amount"] == 80.0

    @pytest.mark.asyncio
    async def test_import_committed_activity_includes_all_counters(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "80.00", "80.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="activity-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="activity-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        activity = await db_session.scalar(
            select(Activity).where(
                Activity.import_id == id2,
                Activity.action_type == "import_committed",
            )
        )
        assert activity is not None
        assert activity.details is not None
        assert "invoices_updated" in activity.details
        assert "invoices_disappeared" in activity.details
        assert "invoices_unchanged" in activity.details

    @pytest.mark.asyncio
    async def test_incoming_duplicate_invoice_number_skipped(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv_bytes = _build_two_invoice_csv(
            [
                ["INV-DUP-1", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-DUP-1", "Beta Corp.", due_str, "200.00", "200.00"],
            ]
        )

        import_id, mapping, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv_bytes, filename="duplicate.csv"
        )
        summary = await confirm_import(db_session, import_id, mapping)

        assert summary["invoices_created"] == 1
        assert summary["errors"] >= 1
        assert any("duplicate" in warning.lower() for warning in summary["warnings"])

    @pytest.mark.asyncio
    async def test_raw_invoice_number_not_overwritten_on_update(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv([["INV 001", "Acme Ltd.", due_str, "75.00", "75.00"]])

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="raw-number-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="raw-number-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        invoice = await db_session.scalar(
            select(Invoice).where(
                Invoice.account_id == test_account.id,
                Invoice.normalized_invoice_number == normalize_invoice_number("INV-001"),
            )
        )
        assert invoice is not None
        assert invoice.invoice_number == "INV-001"
        assert float(invoice.outstanding_amount) == 75.0

    @pytest.mark.asyncio
    async def test_ambiguous_existing_invoice_skipped_with_warning(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv([["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"]])
        csv2 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "75.00", "75.00"],
                ["INV-002", "Beta Corp.", due_str, "50.00", "50.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="ambiguous-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        cust_result = await db_session.execute(
            select(Customer).where(Customer.account_id == test_account.id)
        )
        first_customer = cust_result.scalars().first()
        assert first_customer is not None

        ambiguous_inv = Invoice(
            account_id=test_account.id,
            customer_id=first_customer.id,
            invoice_number="INV/001",
            normalized_invoice_number=normalize_invoice_number("INV-001"),
            due_date=today - timedelta(days=10),
            gross_amount=999.00,
            outstanding_amount=999.00,
            currency="EUR",
            status="open",
            days_overdue=10,
        )
        db_session.add(ambiguous_inv)
        await db_session.flush()

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="ambiguous-2.csv"
        )
        summary = await confirm_import(db_session, id2, map2)

        assert summary["invoices_updated"] == 0
        assert summary["errors"] >= 1
        assert any("ambiguous" in warning.lower() for warning in summary["warnings"])

        invoices = (
            await db_session.execute(
                select(Invoice)
                .where(
                    Invoice.account_id == test_account.id,
                    Invoice.normalized_invoice_number == normalize_invoice_number("INV-001"),
                )
                .order_by(Invoice.invoice_number)
            )
        ).scalars().all()
        assert [float(invoice.outstanding_amount) for invoice in invoices] == [100.0, 999.0]

    @pytest.mark.asyncio
    async def test_customer_aggregates_correct_after_reassignment(self, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv1 = _build_two_invoice_csv(
            [
                ["INV-001", "Acme Ltd.", due_str, "100.00", "100.00"],
                ["INV-002", "Acme Ltd.", due_str, "200.00", "200.00"],
            ]
        )
        csv2 = _build_two_invoice_csv(
            [
                ["INV-001", "Beta Corp.", due_str, "100.00", "100.00"],
                ["INV-002", "Acme Ltd.", due_str, "200.00", "200.00"],
            ]
        )

        id1, map1, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv1, filename="reassign-1.csv"
        )
        await confirm_import(db_session, id1, map1)

        id2, map2, _ = await _create_pending_from_bytes(
            db_session, test_account.id, file_bytes=csv2, filename="reassign-2.csv"
        )
        await confirm_import(db_session, id2, map2)

        acme = await db_session.scalar(
            select(Customer).where(
                Customer.account_id == test_account.id,
                Customer.normalized_name == normalize_customer_name("Acme Ltd."),
            )
        )
        beta = await db_session.scalar(
            select(Customer).where(
                Customer.account_id == test_account.id,
                Customer.normalized_name == normalize_customer_name("Beta Corp."),
            )
        )
        assert acme is not None
        assert beta is not None
        assert float(acme.total_outstanding) == 200.0
        assert float(beta.total_outstanding) == 100.0
