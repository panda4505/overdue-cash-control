"""Shared fixtures for database-backed tests."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.account import Account


def _get_test_db_url() -> str:
    """Return TEST_DATABASE_URL and fail loudly if it is unsafe or missing."""

    get_settings.cache_clear()
    settings = get_settings()
    if not settings.TEST_DATABASE_URL:
        raise RuntimeError(
            "TEST_DATABASE_URL is not configured. Set it in .env or environment variables "
            "to run DB tests. It must point to a dedicated test database."
        )
    if settings.TEST_DATABASE_URL == settings.DATABASE_URL:
        raise RuntimeError(
            "TEST_DATABASE_URL must differ from DATABASE_URL to prevent accidental data loss"
        )
    return settings.TEST_DATABASE_URL


@pytest_asyncio.fixture
async def db_session():
    """Per-test database session on its own engine. No connection pooling.

    Each test gets a fresh engine with NullPool, so asyncpg connections
    are never reused across event loops. Tables are created idempotently.
    Truncated after each test.
    """

    engine = create_async_engine(
        _get_test_db_url(),
        echo=False,
        poolclass=NullPool,
    )

    # Create tables — idempotent, fast if they already exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    session = session_factory()
    yield session

    # Cleanup: rollback, truncate, commit — failures stay visible.
    # close and dispose always run regardless.
    try:
        await session.rollback()
        await session.execute(
            text(
                "TRUNCATE activities, invoices, import_records, "
                "import_templates, customers, users, accounts "
                "RESTART IDENTITY CASCADE"
            )
        )
        await session.commit()
    finally:
        try:
            await session.close()
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def test_account(db_session: AsyncSession) -> Account:
    """Create a test account."""

    account = Account(
        id=uuid.uuid4(),
        company_name="Test Company SAS",
        currency="EUR",
        timezone="Europe/Paris",
        language="fr",
    )
    db_session.add(account)
    await db_session.commit()
    return account


@pytest.fixture(autouse=True)
def _override_upload_dir(tmp_path, monkeypatch):
    """Use a per-test temp directory for uploaded source files."""

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def test_client(db_session):
    """HTTPX test client with the app DB dependency overridden."""

    from httpx import ASGITransport, AsyncClient

    from app.database import get_db
    from app.main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
