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
