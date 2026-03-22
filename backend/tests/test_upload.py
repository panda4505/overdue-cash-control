import hashlib
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from app.dependencies import get_current_user
from app.main import app

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _read_fixture(filename: str) -> bytes:
    return (SAMPLE_DIR / filename).read_bytes()


_fake_user = SimpleNamespace(
    id=uuid.uuid4(),
    account_id=uuid.uuid4(),
    email="test@example.com",
    full_name=None,
    is_active=True,
)


@pytest.fixture(autouse=True)
def _override_auth():
    """Override auth dependency for all tests in this file."""

    app.dependency_overrides[get_current_user] = lambda: _fake_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


class TestUploadEndpoint:
    """Tests for POST /upload."""

    @pytest.mark.asyncio
    async def test_upload_csv_succeeds(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("pohoda_ar_export.csv", file_bytes, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_rows"] == 15
        assert data["file_hash"] is not None
        assert len(data["file_hash"]) == 64
        assert data["mapping"] is not None
        assert data["mapping"]["success"] is True
        assert len(data["sample_rows"]) > 0

    @pytest.mark.asyncio
    async def test_upload_french_csv(self):
        file_bytes = _read_fixture("french_ar_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("french_ar_export.csv", file_bytes, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_rows"] == 12
        assert data["mapping"]["method"] == "deterministic"

    @pytest.mark.asyncio
    async def test_upload_italian_csv(self):
        file_bytes = _read_fixture("italian_ar_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("italian_ar_export.csv", file_bytes, "text/csv")},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["decimal_separator"] == ","
        assert data["thousands_separator"] == "."

    @pytest.mark.asyncio
    async def test_upload_xlsx_succeeds(self):
        file_bytes = _read_fixture("german_ar_export.xlsx")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={
                    "file": (
                        "german_ar_export.xlsx",
                        file_bytes,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total_rows"] == 10
        assert data["mapping"] is not None
        assert data["mapping"]["success"] is True
        assert data["sheet_name"] == "Rechnungen"

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("report.pdf", b"fake pdf content", "application/pdf")},
            )
        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_file(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("empty.csv", b"", "text/csv")},
            )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_returns_correct_hash(self):
        file_bytes = _read_fixture("fakturoid_ar_export.csv")
        expected_hash = hashlib.sha256(file_bytes).hexdigest()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("fakturoid_ar_export.csv", file_bytes, "text/csv")},
            )
        data = response.json()
        assert data["file_hash"] == expected_hash

    @pytest.mark.asyncio
    async def test_upload_response_is_json_serializable(self):
        """The full response should be valid JSON (no date objects, no DataFrames)."""
        file_bytes = _read_fixture("messy_generic_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("messy_generic_export.csv", file_bytes, "text/csv")},
            )
        json.dumps(response.json())

    @pytest.mark.asyncio
    async def test_upload_sample_rows_have_original_headers(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("pohoda_ar_export.csv", file_bytes, "text/csv")},
            )
        data = response.json()
        first_row = data["sample_rows"][0]
        assert "Číslo faktury" in first_row
        assert "invoice_number" not in first_row

    @pytest.mark.asyncio
    async def test_upload_mapping_includes_field_details(self):
        file_bytes = _read_fixture("fakturoid_ar_export.csv")
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/upload",
                files={"file": ("fakturoid_ar_export.csv", file_bytes, "text/csv")},
            )
        data = response.json()
        mappings = data["mapping"]["mappings"]
        for mapping in mappings:
            assert "source_column" in mapping
            assert "target_field" in mapping
            assert "confidence" in mapping
            assert "method" in mapping
            assert "tier" in mapping
