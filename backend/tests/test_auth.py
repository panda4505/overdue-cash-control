"""Tests for auth endpoints — requires PostgreSQL."""

import uuid

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


@pytest.mark.asyncio
class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"
        assert "account_id" in data["user"]

    async def test_register_creates_eur_defaults(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 201
        token = resp.json()["access_token"]
        me_resp = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        account = me_resp.json()["account"]
        assert account["currency"] == "EUR"
        assert account["timezone"] == "Europe/Paris"
        assert account["language"] == "en"
        assert account["company_name"] is None

    async def test_register_duplicate_email(self, client):
        await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "different123"},
        )
        assert resp.status_code == 409

    async def test_register_duplicate_email_case_insensitive(self, client):
        await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/register",
            json={"email": "Test@Example.COM", "password": "different123"},
        )
        assert resp.status_code == 409

    async def test_register_short_password(self, client):
        resp = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "short"},
        )
        assert resp.status_code == 400


@pytest.mark.asyncio
class TestLogin:
    async def test_login_success(self, client):
        await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "password123"},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    async def test_login_case_insensitive_email(self, client):
        await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "Test@Example.COM", "password": "password123"},
        )
        assert resp.status_code == 200

    async def test_login_wrong_password(self, client):
        await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        resp = await client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401

    async def test_login_nonexistent_email(self, client):
        resp = await client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "password123"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestMe:
    async def test_me_with_token(self, client):
        reg = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = await client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"]["email"] == "test@example.com"
        assert "account" in data

    async def test_me_without_token(self, client):
        resp = await client.get("/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token(self, client):
        resp = await client.get(
            "/auth/me", headers={"Authorization": "Bearer invalid-token"}
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestUpdateAccount:
    async def test_update_company_name(self, client):
        reg = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = await client.patch(
            "/auth/account",
            headers={"Authorization": f"Bearer {token}"},
            json={"company_name": "ACME s.r.o."},
        )
        assert resp.status_code == 200
        assert resp.json()["account"]["company_name"] == "ACME s.r.o."

    async def test_update_partial(self, client):
        reg = await client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = await client.patch(
            "/auth/account",
            headers={"Authorization": f"Bearer {token}"},
            json={"currency": "CZK"},
        )
        assert resp.status_code == 200
        assert resp.json()["account"]["currency"] == "CZK"
        assert resp.json()["account"]["timezone"] == "Europe/Paris"

    async def test_update_account_without_auth(self, client):
        resp = await client.patch(
            "/auth/account",
            json={"company_name": "Hacker Corp"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestAccountIsolation:
    async def test_upload_to_other_account_forbidden(self, client):
        import io

        reg_a = await client.post(
            "/auth/register",
            json={"email": "a@example.com", "password": "password123"},
        )
        account_a_id = reg_a.json()["user"]["account_id"]

        reg_b = await client.post(
            "/auth/register",
            json={"email": "b@example.com", "password": "password123"},
        )
        token_b = reg_b.json()["access_token"]

        csv_content = b"Invoice,Customer,Due Date,Amount\nINV-001,ACME,2024-01-15,1000"
        resp = await client.post(
            f"/accounts/{account_a_id}/imports/upload",
            headers={"Authorization": f"Bearer {token_b}"},
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 403

    async def test_confirm_other_accounts_import_forbidden(self, client):
        import io

        reg_a = await client.post(
            "/auth/register",
            json={"email": "a@example.com", "password": "password123"},
        )
        token_a = reg_a.json()["access_token"]
        account_a_id = reg_a.json()["user"]["account_id"]

        csv_content = b"Invoice,Customer,Due Date,Amount\nINV-001,ACME,2024-01-15,1000"
        upload_resp = await client.post(
            f"/accounts/{account_a_id}/imports/upload",
            headers={"Authorization": f"Bearer {token_a}"},
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        import_id = upload_resp.json()["import_id"]

        reg_b = await client.post(
            "/auth/register",
            json={"email": "b@example.com", "password": "password123"},
        )
        token_b = reg_b.json()["access_token"]

        resp = await client.post(
            f"/imports/{import_id}/confirm",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "mapping": {"invoice_number": "Invoice", "customer_name": "Customer",
                            "due_date": "Due Date", "outstanding_amount": "Amount"},
                "scope_type": "unknown",
            },
        )
        assert resp.status_code == 403


@pytest.mark.asyncio
class TestProtectedRoutes:
    async def test_upload_without_auth(self, client):
        import io

        csv_content = b"Invoice,Customer,Due Date,Amount\nINV-001,ACME,2024-01-15,1000"
        resp = await client.post(
            f"/accounts/{uuid.uuid4()}/imports/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 401

    async def test_confirm_without_auth(self, client):
        resp = await client.post(
            f"/imports/{uuid.uuid4()}/confirm",
            json={"mapping": {}, "scope_type": "unknown"},
        )
        assert resp.status_code == 401

    async def test_save_template_without_auth(self, client):
        resp = await client.post(
            f"/imports/{uuid.uuid4()}/save-template",
            json={"name": "test", "mapping": {}},
        )
        assert resp.status_code == 401

    async def test_raw_upload_without_auth(self, client):
        import io

        csv_content = b"Invoice,Customer,Due Date,Amount\nINV-001,ACME,2024-01-15,1000"
        resp = await client.post(
            "/upload",
            files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
class TestTestEmailRemoved:
    async def test_test_email_endpoint_gone(self, client):
        resp = await client.get("/test-email")
        assert resp.status_code in (404, 405)
