import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.ingestion import ingest_file

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _read_fixture(filename: str) -> bytes:
    return (SAMPLE_DIR / filename).read_bytes()


def _make_webhook_payload(email_id="test-email-123", attachments_meta=None):
    return {
        "type": "email.received",
        "data": {
            "email_id": email_id,
            "from": "accountant@example.com",
            "to": ["import@tuaentoocl.resend.app"],
            "subject": "AR Export March 2026",
            "attachments": attachments_meta or [],
        },
    }


class MockResponse:
    def __init__(
        self,
        *,
        status_code: int,
        json_data: dict | None = None,
        content: bytes = b"",
        text: str = "",
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.content = content
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON data configured for this response")
        return self._json_data


class TestIngestionParity:
    """Same file bytes must produce identical results via upload vs email paths."""

    @pytest.mark.asyncio
    async def test_parity_all_fixtures(self):
        fixtures = [
            "pohoda_ar_export.csv",
            "fakturoid_ar_export.csv",
            "messy_generic_export.csv",
            "french_ar_export.csv",
            "italian_ar_export.csv",
        ]

        for fixture in fixtures:
            file_bytes = _read_fixture(fixture)
            upload_dict = (await ingest_file(file_bytes, fixture, method="upload")).to_dict()
            email_dict = (await ingest_file(file_bytes, fixture, method="email")).to_dict()

            assert upload_dict["method"] == "upload"
            assert email_dict["method"] == "email"

            upload_dict["method"] = None
            email_dict["method"] = None

            assert upload_dict == email_dict

    @pytest.mark.asyncio
    async def test_parity_hash_identical(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")

        result_upload = await ingest_file(file_bytes, "pohoda_ar_export.csv", method="upload")
        result_email = await ingest_file(file_bytes, "pohoda_ar_export.csv", method="email")

        assert result_upload.file_hash == result_email.file_hash

    @pytest.mark.asyncio
    async def test_parity_mapping_identical(self):
        file_bytes = _read_fixture("french_ar_export.csv")

        result_upload = await ingest_file(file_bytes, "french_ar_export.csv", method="upload")
        result_email = await ingest_file(file_bytes, "french_ar_export.csv", method="email")

        assert result_upload.mapping is not None
        assert result_email.mapping is not None
        assert len(result_upload.mapping.mappings) == len(result_email.mapping.mappings)
        assert [
            (mapping.source_column, mapping.target_field) for mapping in result_upload.mapping.mappings
        ] == [
            (mapping.source_column, mapping.target_field) for mapping in result_email.mapping.mappings
        ]


class TestWebhookEndpoint:
    """Tests for POST /webhooks/resend/inbound with ingestion wired up."""

    @pytest.mark.asyncio
    async def test_webhook_processes_csv_attachment(self):
        file_bytes = _read_fixture("pohoda_ar_export.csv")
        attachments_payload = {
            "data": [
                {
                    "filename": "test.csv",
                    "download_url": "https://example.com/dl/test.csv",
                    "content_type": "text/csv",
                }
            ]
        }

        async def mock_get(self, url, *args, **kwargs):
            if url == "https://api.resend.com/emails/receiving/test-email-123/attachments":
                return MockResponse(
                    status_code=200,
                    json_data=attachments_payload,
                    text=json.dumps(attachments_payload),
                )
            if url == "https://example.com/dl/test.csv":
                return MockResponse(status_code=200, content=file_bytes)
            raise AssertionError(f"Unexpected URL requested: {url}")

        transport = ASGITransport(app=app)
        with patch("httpx.AsyncClient.get", new=mock_get):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/webhooks/resend/inbound",
                    json=_make_webhook_payload(attachments_meta=[{"filename": "test.csv"}]),
                )

        assert response.status_code == 200
        data = response.json()
        assert data["attachments_processed"] == 1
        assert data["results"][0]["success"] is True
        assert data["results"][0]["method"] == "email"
        assert data["results"][0]["total_rows"] == 15

    @pytest.mark.asyncio
    async def test_webhook_skips_unsupported_file_type(self):
        attachments_payload = {
            "data": [
                {
                    "filename": "report.pdf",
                    "download_url": "https://example.com/dl/report.pdf",
                    "content_type": "application/pdf",
                }
            ]
        }

        async def mock_get(self, url, *args, **kwargs):
            if url == "https://api.resend.com/emails/receiving/test-email-123/attachments":
                return MockResponse(
                    status_code=200,
                    json_data=attachments_payload,
                    text=json.dumps(attachments_payload),
                )
            if url == "https://example.com/dl/report.pdf":
                return MockResponse(status_code=200, content=b"%PDF-1.7")
            raise AssertionError(f"Unexpected URL requested: {url}")

        transport = ASGITransport(app=app)
        with patch("httpx.AsyncClient.get", new=mock_get):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/webhooks/resend/inbound",
                    json=_make_webhook_payload(attachments_meta=[{"filename": "report.pdf"}]),
                )

        assert response.status_code == 200
        data = response.json()
        assert data["attachments_processed"] == 0
        assert data["attachments_skipped"][0]["filename"] == "report.pdf"
        assert "Unsupported" in data["attachments_skipped"][0]["reason"]

    @pytest.mark.asyncio
    async def test_webhook_no_attachments(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/resend/inbound",
                json=_make_webhook_payload(attachments_meta=[]),
            )

        assert response.status_code == 200
        assert response.json()["attachments_count"] == 0

    @pytest.mark.asyncio
    async def test_webhook_non_email_event_returns_200(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/webhooks/resend/inbound",
                json={"type": "email.bounced"},
            )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_handles_download_failure(self):
        attachments_payload = {
            "data": [
                {
                    "filename": "test.csv",
                    "download_url": "https://example.com/dl/test.csv",
                    "content_type": "text/csv",
                }
            ]
        }

        async def mock_get(self, url, *args, **kwargs):
            if url == "https://api.resend.com/emails/receiving/test-email-123/attachments":
                return MockResponse(
                    status_code=200,
                    json_data=attachments_payload,
                    text=json.dumps(attachments_payload),
                )
            if url == "https://example.com/dl/test.csv":
                return MockResponse(status_code=500, content=b"")
            raise AssertionError(f"Unexpected URL requested: {url}")

        transport = ASGITransport(app=app)
        with patch("httpx.AsyncClient.get", new=mock_get):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/webhooks/resend/inbound",
                    json=_make_webhook_payload(attachments_meta=[{"filename": "test.csv"}]),
                )

        assert response.status_code == 200
        data = response.json()
        assert data["attachments_processed"] == 0
        assert "Download failed" in data["attachments_skipped"][0]["reason"]

    @pytest.mark.asyncio
    async def test_webhook_multiple_attachments_mixed(self):
        pohoda_bytes = _read_fixture("pohoda_ar_export.csv")
        french_bytes = _read_fixture("french_ar_export.csv")
        attachments_payload = {
            "data": [
                {
                    "filename": "a.csv",
                    "download_url": "https://example.com/dl/a.csv",
                    "content_type": "text/csv",
                },
                {
                    "filename": "report.pdf",
                    "download_url": "https://example.com/dl/report.pdf",
                    "content_type": "application/pdf",
                },
                {
                    "filename": "c.csv",
                    "download_url": "https://example.com/dl/c.csv",
                    "content_type": "text/csv",
                },
            ]
        }

        async def mock_get(self, url, *args, **kwargs):
            if url == "https://api.resend.com/emails/receiving/test-email-123/attachments":
                return MockResponse(
                    status_code=200,
                    json_data=attachments_payload,
                    text=json.dumps(attachments_payload),
                )
            if url == "https://example.com/dl/a.csv":
                return MockResponse(status_code=200, content=pohoda_bytes)
            if url == "https://example.com/dl/report.pdf":
                return MockResponse(status_code=200, content=b"%PDF-1.7")
            if url == "https://example.com/dl/c.csv":
                return MockResponse(status_code=200, content=french_bytes)
            raise AssertionError(f"Unexpected URL requested: {url}")

        transport = ASGITransport(app=app)
        with patch("httpx.AsyncClient.get", new=mock_get):
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/webhooks/resend/inbound",
                    json=_make_webhook_payload(
                        attachments_meta=[
                            {"filename": "a.csv"},
                            {"filename": "b.pdf"},
                            {"filename": "c.csv"},
                        ]
                    ),
                )

        assert response.status_code == 200
        data = response.json()
        assert data["attachments_processed"] == 2
        assert len(data["attachments_skipped"]) == 1
        assert len(data["results"]) == 2
        assert data["results"][0]["success"] is True
        assert data["results"][1]["success"] is True
