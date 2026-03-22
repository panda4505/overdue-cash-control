"""Tests for template persistence and auto-apply — requires PostgreSQL."""

import io

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app

settings = get_settings()

TABLES_TO_TRUNCATE = [
    "activities", "invoices", "import_records",
    "import_templates", "customers", "users", "accounts",
]


@pytest_asyncio.fixture
async def db_session():
    test_url = settings.TEST_DATABASE_URL
    if not test_url:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_async_engine(test_url, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        for table in TABLES_TO_TRUNCATE:
            await session.execute(text(f"TRUNCATE {table} CASCADE"))
        await session.commit()

    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_context(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "template-test@example.com", "password": "password123"},
    )
    data = resp.json()
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "account_id": data["user"]["account_id"],
    }


SAMPLE_CSV = b"Invoice Number,Customer Name,Due Date,Amount Due\nINV-001,ACME Corp,2024-06-15,1500.00\nINV-002,Beta Ltd,2024-07-01,2300.50"


@pytest.mark.asyncio
class TestSaveTemplate:
    async def test_save_template_on_mapping_confirm(self, client, auth_context):
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload_resp = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        assert upload_resp.status_code == 200
        import_id = upload_resp.json()["import_id"]

        template_resp = await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={
                "name": "Monthly AR Export",
                "mapping": {
                    "invoice_number": "Invoice Number",
                    "customer_name": "Customer Name",
                    "due_date": "Due Date",
                    "outstanding_amount": "Amount Due",
                },
                "scope_type": "full_snapshot",
                "delimiter": ",",
                "decimal_separator": ".",
            },
        )
        assert template_resp.status_code == 200
        template = template_resp.json()["template"]
        assert template["name"] == "Monthly AR Export"
        assert template["scope_type"] == "full_snapshot"

    async def test_save_template_idempotent(self, client, auth_context):
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload_resp = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        import_id = upload_resp.json()["import_id"]

        mapping = {
            "invoice_number": "Invoice Number",
            "customer_name": "Customer Name",
            "due_date": "Due Date",
            "outstanding_amount": "Amount Due",
        }

        resp1 = await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={"name": "Version 1", "mapping": mapping},
        )
        template_id_1 = resp1.json()["template"]["id"]

        resp2 = await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={"name": "Version 2", "mapping": mapping},
        )
        template_id_2 = resp2.json()["template"]["id"]

        assert template_id_1 == template_id_2
        assert resp2.json()["template"]["name"] == "Version 2"

    async def test_save_template_wrong_account(self, client, auth_context):
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload_resp = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("test.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        import_id = upload_resp.json()["import_id"]

        reg_b = await client.post(
            "/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        token_b = reg_b.json()["access_token"]

        resp = await client.post(
            f"/imports/{import_id}/save-template",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "name": "Stolen Template",
                "mapping": {"invoice_number": "Invoice Number"},
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestTemplateAutoApply:
    async def test_second_upload_applies_saved_template(self, client, auth_context):
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload1 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("export1.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        import_id = upload1.json()["import_id"]

        await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={
                "name": "AR Export",
                "mapping": {
                    "invoice_number": "Invoice Number",
                    "customer_name": "Customer Name",
                    "due_date": "Due Date",
                    "outstanding_amount": "Amount Due",
                },
                "scope_type": "full_snapshot",
                "delimiter": ",",
                "decimal_separator": ".",
            },
        )

        csv2 = b"Invoice Number,Customer Name,Due Date,Amount Due\nINV-003,Gamma,2024-08-01,500.00"
        upload2 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("export2.csv", io.BytesIO(csv2), "text/csv")},
        )
        assert upload2.status_code == 200
        data = upload2.json()
        assert "applied_template" in data
        assert data["applied_template"]["name"] == "AR Export"

    async def test_no_auto_apply_different_headers(self, client, auth_context):
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload1 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("export1.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        import_id = upload1.json()["import_id"]
        await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={
                "name": "AR Export",
                "mapping": {
                    "invoice_number": "Invoice Number",
                    "customer_name": "Customer Name",
                    "due_date": "Due Date",
                    "outstanding_amount": "Amount Due",
                },
                "scope_type": "full_snapshot",
                "delimiter": ",",
            },
        )

        csv_different = b"Facture,Client,Echeance,Montant\nF-001,Test,2024-01-01,100"
        upload2 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("french.csv", io.BytesIO(csv_different), "text/csv")},
        )
        assert upload2.status_code == 200
        assert upload2.json().get("applied_template") is None

    async def test_no_auto_apply_extra_columns(self, client, auth_context):
        """Template not applied when file has columns beyond the mapped set."""
        headers = auth_context["headers"]
        account_id = auth_context["account_id"]

        upload1 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("export1.csv", io.BytesIO(SAMPLE_CSV), "text/csv")},
        )
        import_id = upload1.json()["import_id"]
        await client.post(
            f"/imports/{import_id}/save-template",
            headers=headers,
            json={
                "name": "AR Export",
                "mapping": {
                    "invoice_number": "Invoice Number",
                    "customer_name": "Customer Name",
                    "due_date": "Due Date",
                    "outstanding_amount": "Amount Due",
                },
                "scope_type": "full_snapshot",
                "delimiter": ",",
            },
        )

        csv_extra = (
            b"Invoice Number,Customer Name,Due Date,Amount Due,Notes\n"
            b"INV-001,Test,2024-01-01,100,some note"
        )
        upload2 = await client.post(
            f"/accounts/{account_id}/imports/upload",
            headers=headers,
            files={"file": ("wide.csv", io.BytesIO(csv_extra), "text/csv")},
        )
        assert upload2.status_code == 200
        assert upload2.json().get("applied_template") is None
