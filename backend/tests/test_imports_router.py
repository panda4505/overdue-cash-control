from __future__ import annotations

import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _read_fixture(filename: str) -> bytes:
    return (SAMPLE_DIR / filename).read_bytes()


def _mapping_from_preview(preview: dict) -> dict[str, str]:
    assert preview["mapping"] is not None
    return {
        mapping["target_field"]: mapping["source_column"]
        for mapping in preview["mapping"]["mappings"]
    }


def _content_type(filename: str) -> str:
    if filename.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if filename.endswith(".tsv"):
        return "text/tab-separated-values"
    return "text/csv"


class TestImportsRouter:
    @pytest.mark.asyncio
    async def test_upload_returns_preview_and_import_id(self, test_client, test_account):
        response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["import_id"] is not None
        assert data["preview"]["total_rows"] == 12
        assert data["preview"]["mapping"]["success"] is True
        assert data["duplicate_warning"] is None

    @pytest.mark.asyncio
    async def test_confirm_returns_summary(self, test_client, test_account):
        upload_response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("italian_ar_export.csv", _read_fixture("italian_ar_export.csv"), "text/csv")},
        )
        upload_data = upload_response.json()
        confirm_response = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": _mapping_from_preview(upload_data["preview"])},
        )

        assert confirm_response.status_code == 200
        data = confirm_response.json()
        assert data["status"] == "confirmed"
        assert data["invoices_created"] > 0
        assert "change_set" not in data

    @pytest.mark.asyncio
    async def test_upload_unsupported_file_type(self, test_client, test_account):
        response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("report.pdf", b"fake", "application/pdf")},
        )

        assert response.status_code == 400
        assert "Unsupported" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_file(self, test_client, test_account):
        response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("empty.csv", b"", "text/csv")},
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_upload_nonexistent_account(self, test_client):
        response = await test_client.post(
            f"/accounts/{uuid.uuid4()}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_nonexistent_import(self, test_client):
        response = await test_client.post(
            f"/imports/{uuid.uuid4()}/confirm",
            json={"mapping": {"invoice_number": "Invoice Number"}},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_already_confirmed(self, test_client, test_account):
        upload_response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )
        upload_data = upload_response.json()
        mapping = _mapping_from_preview(upload_data["preview"])

        first_confirm = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": mapping},
        )
        second_confirm = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": mapping},
        )

        assert first_confirm.status_code == 200
        assert second_confirm.status_code == 409

    @pytest.mark.asyncio
    async def test_confirm_invalid_mapping_rejected(self, test_client, test_account):
        upload_response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )
        upload_data = upload_response.json()
        mapping = _mapping_from_preview(upload_data["preview"])
        mapping["invoice_number"] = "Missing Column"

        response = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": mapping},
        )

        assert response.status_code == 400
        assert "not in file" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_confirm_with_scope_type_full_snapshot(self, test_client, test_account):
        upload_response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )
        upload_data = upload_response.json()
        mapping = _mapping_from_preview(upload_data["preview"])

        response = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": mapping, "scope_type": "full_snapshot"},
        )

        assert response.status_code == 200
        assert response.json()["scope_type"] == "full_snapshot"

    @pytest.mark.asyncio
    async def test_confirm_with_invalid_scope_type_rejected(self, test_client, test_account):
        upload_response = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("french_ar_export.csv", _read_fixture("french_ar_export.csv"), "text/csv")},
        )
        upload_data = upload_response.json()
        mapping = _mapping_from_preview(upload_data["preview"])

        response = await test_client.post(
            f"/imports/{upload_data['import_id']}/confirm",
            json={"mapping": mapping, "scope_type": "invalid_value"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_confirm_accepts_merge_decisions(self, test_client, db_session, test_account):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv_content = (
            "Invoice Number,Client Name,Due Date,Amount Due,Total Amount\n"
            f"INV-001,Acme Ltd.,{due_str},100.00,100.00\n"
        ).encode("utf-8")

        upload_resp = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert upload_resp.status_code == 200
        import_id = upload_resp.json()["import_id"]
        mapping = {
            mapping["target_field"]: mapping["source_column"]
            for mapping in upload_resp.json()["preview"]["mapping"]["mappings"]
        }

        confirm_resp = await test_client.post(
            f"/imports/{import_id}/confirm",
            json={"mapping": mapping, "scope_type": "unknown", "merge_decisions": {}},
        )

        assert confirm_resp.status_code == 200
        assert "customers_merged" in confirm_resp.json()

    @pytest.mark.asyncio
    async def test_confirm_invalid_merge_decision_returns_400(
        self,
        test_client,
        db_session,
        test_account,
    ):
        today = date.today()
        due_str = (today - timedelta(days=10)).isoformat()
        csv_content = (
            "Invoice Number,Client Name,Due Date,Amount Due,Total Amount\n"
            f"INV-001,Acme Ltd.,{due_str},100.00,100.00\n"
        ).encode("utf-8")

        upload_resp = await test_client.post(
            f"/accounts/{test_account.id}/imports/upload",
            files={"file": ("test.csv", csv_content, "text/csv")},
        )

        assert upload_resp.status_code == 200
        import_id = upload_resp.json()["import_id"]
        mapping = {
            mapping["target_field"]: mapping["source_column"]
            for mapping in upload_resp.json()["preview"]["mapping"]["mappings"]
        }

        fake_id = str(uuid.uuid4())
        confirm_resp = await test_client.post(
            f"/imports/{import_id}/confirm",
            json={
                "mapping": mapping,
                "scope_type": "unknown",
                "merge_decisions": {"acme": fake_id},
            },
        )

        assert confirm_resp.status_code == 400
        assert "unknown customer ID" in confirm_resp.json()["detail"]
