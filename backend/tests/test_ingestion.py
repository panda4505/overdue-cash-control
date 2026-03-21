import hashlib
import json
from pathlib import Path

import pytest

from app.services.ingestion import ingest_file

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _read_fixture(filename: str) -> bytes:
    return (SAMPLE_DIR / filename).read_bytes()


class TestIngestionService:
    """Tests for the shared ingest_file() function."""

    @pytest.mark.asyncio
    async def test_pohoda_ingestion_succeeds(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        result = await ingest_file(file_bytes, "pohoda_ar_export.csv")
        assert result.success is True
        assert result.total_rows == 15
        assert result.mapping is not None
        assert result.mapping.success is True
        assert len(result.sample_rows) <= 10
        assert result.method == "upload"

    @pytest.mark.asyncio
    async def test_french_ingestion_succeeds(self):
        file_bytes = _read_fixture("french_ar_export.csv")
        result = await ingest_file(file_bytes, "french_ar_export.csv")
        assert result.success is True
        assert result.total_rows == 12
        assert result.encoding is not None
        assert result.mapping is not None
        assert result.mapping.method == "deterministic"

    @pytest.mark.asyncio
    async def test_italian_ingestion_succeeds(self):
        file_bytes = _read_fixture("italian_ar_export.csv")
        result = await ingest_file(file_bytes, "italian_ar_export.csv")
        assert result.success is True
        assert result.total_rows == 12
        assert result.decimal_separator == ","
        assert result.thousands_separator == "."

    @pytest.mark.asyncio
    async def test_german_xlsx_ingestion_succeeds(self):
        file_bytes = _read_fixture("german_ar_export.xlsx")
        result = await ingest_file(file_bytes, "german_ar_export.xlsx")
        assert result.success is True
        assert result.total_rows == 10
        assert result.mapping is not None
        assert result.mapping.success is True
        assert result.sheet_name == "Rechnungen"
        assert len(result.sample_rows) > 0
        assert result.method == "upload"

    @pytest.mark.asyncio
    async def test_file_hash_is_sha256(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        expected_hash = hashlib.sha256(file_bytes).hexdigest()
        result = await ingest_file(file_bytes, "pohoda_ar_export.csv")
        assert result.file_hash == expected_hash
        assert len(result.file_hash) == 64

    @pytest.mark.asyncio
    async def test_file_size_recorded(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        result = await ingest_file(file_bytes, "pohoda_ar_export.csv")
        assert result.file_size_bytes == len(file_bytes)

    @pytest.mark.asyncio
    async def test_same_file_produces_same_hash(self):
        """Duplicate detection foundation: same bytes -> same hash."""

        file_bytes = _read_fixture("fakturoid_ar_export.csv")
        result1 = await ingest_file(file_bytes, "fakturoid_ar_export.csv")
        result2 = await ingest_file(file_bytes, "fakturoid_ar_export.csv")
        assert result1.file_hash == result2.file_hash

    @pytest.mark.asyncio
    async def test_sample_rows_are_serializable(self):
        """Sample rows should contain only JSON-safe types."""

        file_bytes = _read_fixture("messy_generic_export.csv")
        result = await ingest_file(file_bytes, "messy_generic_export.csv")
        json.dumps(result.sample_rows)

    @pytest.mark.asyncio
    async def test_sample_rows_use_original_headers(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        result = await ingest_file(file_bytes, "pohoda_ar_export.csv")
        assert len(result.sample_rows) > 0
        first_row = result.sample_rows[0]
        assert "Číslo faktury" in first_row
        assert "invoice_number" not in first_row

    @pytest.mark.asyncio
    async def test_empty_file_returns_failure(self):
        result = await ingest_file(b"", "empty.csv")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_unsupported_file_returns_failure(self):
        result = await ingest_file(b"some bytes", "document.pdf")
        assert result.success is False
        assert "Unsupported" in (result.error or "")

    @pytest.mark.asyncio
    async def test_method_parameter_recorded(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        result_upload = await ingest_file(file_bytes, "pohoda_ar_export.csv", method="upload")
        result_email = await ingest_file(file_bytes, "pohoda_ar_export.csv", method="email")
        assert result_upload.method == "upload"
        assert result_email.method == "email"

    @pytest.mark.asyncio
    async def test_template_passed_through_to_mapper(self):
        """When an existing template is provided, it should be used by the mapper."""

        file_bytes = _read_fixture("pohoda_ar_export.csv")
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Odběratel",
            "due_date": "Datum splatnosti",
            "outstanding_amount": "Zbývá uhradit",
            "gross_amount": "Celkem s DPH",
        }
        result = await ingest_file(
            file_bytes,
            "pohoda_ar_export.csv",
            existing_template=template,
        )
        assert result.success is True
        assert result.mapping is not None
        assert result.mapping.method in ("template", "mixed")

    @pytest.mark.asyncio
    async def test_warnings_aggregated_from_parser_and_mapper(self):
        """Warnings from both parser and mapper should appear in the result."""

        file_bytes = _read_fixture("pohoda_ar_export.csv")
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Odběratel",
            "due_date": "Datum splatnosti",
            "outstanding_amount": "Zbývá uhradit",
            "gross_amount": "NONEXISTENT",
        }
        result = await ingest_file(
            file_bytes,
            "pohoda_ar_export.csv",
            existing_template=template,
        )
        assert any("NONEXISTENT" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_all_fixtures_ingest_successfully(self):
        """Smoke test: all 6 fixtures should ingest without errors."""

        fixtures = [
            "pohoda_ar_export.csv",
            "fakturoid_ar_export.csv",
            "messy_generic_export.csv",
            "french_ar_export.csv",
            "italian_ar_export.csv",
            "german_ar_export.xlsx",
        ]
        for fixture in fixtures:
            file_bytes = _read_fixture(fixture)
            result = await ingest_file(file_bytes, fixture)
            assert result.success is True, f"Failed on {fixture}: {result.error}"
            assert result.total_rows > 0, f"No rows on {fixture}"
            assert result.mapping is not None, f"No mapping on {fixture}"
            assert len(result.sample_rows) > 0, f"No sample rows on {fixture}"
