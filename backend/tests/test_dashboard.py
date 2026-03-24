"""Tests for the dashboard endpoint."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import Account
from app.models.activity import Activity
from app.models.customer import Customer
from app.models.import_record import ImportRecord
from app.models.invoice import Invoice
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from app.services.normalization import normalize_customer_name


async def _create_test_customer(
    db: AsyncSession,
    account_id,
    *,
    name: str,
    deleted_at: datetime | None = None,
) -> Customer:
    customer = Customer(
        account_id=account_id,
        name=name,
        normalized_name=normalize_customer_name(name),
        deleted_at=deleted_at,
    )
    db.add(customer)
    await db.flush()
    return customer


async def _create_test_import(
    db: AsyncSession,
    account_id,
    *,
    status: str = "confirmed",
    method: str = "upload",
    original_filename: str = "receivables.csv",
    confirmed_at: datetime | None = None,
    invoices_created: int = 0,
    invoices_updated: int = 0,
    invoices_disappeared: int = 0,
    invoices_unchanged: int = 0,
) -> ImportRecord:
    import_record = ImportRecord(
        account_id=account_id,
        method=method,
        original_filename=original_filename,
        file_hash=uuid.uuid4().hex,
        status=status,
        confirmed_at=confirmed_at,
        invoices_created=invoices_created,
        invoices_updated=invoices_updated,
        invoices_disappeared=invoices_disappeared,
        invoices_unchanged=invoices_unchanged,
    )
    db.add(import_record)
    await db.flush()
    return import_record


async def _create_test_invoice(
    db,
    account_id,
    customer_id,
    import_id,
    *,
    invoice_number,
    outstanding_amount,
    due_date,
    status="open",
    deleted_at=None,
):
    """Insert a test invoice with the given parameters."""
    invoice = Invoice(
        account_id=account_id,
        customer_id=customer_id,
        invoice_number=invoice_number,
        normalized_invoice_number=invoice_number.lower(),
        due_date=due_date,
        outstanding_amount=Decimal(str(outstanding_amount)),
        gross_amount=Decimal(str(outstanding_amount)),
        currency="EUR",
        status=status,
        days_overdue=0,  # intentionally stale — dashboard must not use this
        action_count=0,
        first_seen_import_id=import_id,
        last_updated_import_id=import_id,
        deleted_at=deleted_at,
    )
    db.add(invoice)
    await db.flush()
    return invoice


async def _create_test_activity(
    db: AsyncSession,
    account_id,
    *,
    action_type: str,
    invoice_id=None,
    customer_id=None,
    import_id=None,
    details: dict | None = None,
    created_at: datetime | None = None,
) -> Activity:
    activity = Activity(
        account_id=account_id,
        invoice_id=invoice_id,
        customer_id=customer_id,
        import_id=import_id,
        action_type=action_type,
        details=details,
        performed_by="system",
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(activity)
    await db.flush()
    return activity


def _bucket_map(payload: dict) -> dict[str, dict]:
    return {bucket["label"]: bucket for bucket in payload["aging_buckets"]}


def _sum_overdue_bucket_amounts(payload: dict) -> Decimal:
    return sum(
        Decimal(bucket["amount"])
        for bucket in payload["aging_buckets"]
        if bucket["is_overdue"]
    )


@pytest.mark.asyncio
async def test_dashboard_empty_account(
    test_client: AsyncClient,
    auth_headers: dict,
    test_account: Account,
):
    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_overdue_amount"] == "0.00"
    assert data["total_overdue_count"] == 0
    assert data["overdue_today_count"] == 0
    assert data["overdue_today_amount"] == "0.00"
    assert data["disputed_count"] == 0
    assert data["possibly_paid_count"] == 0
    assert len(data["aging_buckets"]) == 5
    assert all(bucket["count"] == 0 for bucket in data["aging_buckets"])
    assert data["top_exposure"] is None
    assert data["recent_changes"] == []
    assert data["last_import"] is None
    assert data["is_data_stale"] is True
    assert data["first_import_at"] is None


@pytest.mark.asyncio
async def test_dashboard_with_overdue_invoices(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Acme SA")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
        original_filename="snapshot.csv",
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="CUR-001",
        outstanding_amount="400.00",
        due_date=date.today() + timedelta(days=1),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-001",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=1),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-002",
        outstanding_amount="200.00",
        due_date=date.today() - timedelta(days=8),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-003",
        outstanding_amount="300.00",
        due_date=date.today() - timedelta(days=31),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-004",
        outstanding_amount="500.00",
        due_date=date.today() - timedelta(days=75),
        status="possibly_paid",
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    buckets = _bucket_map(data)

    assert data["total_overdue_amount"] == "1100.00"
    assert data["total_overdue_count"] == 4
    assert buckets["Current"]["count"] == 1
    assert buckets["Current"]["amount"] == "400.00"
    assert buckets["1–7 days"]["count"] == 1
    assert buckets["1–7 days"]["amount"] == "100.00"
    assert buckets["8–30 days"]["count"] == 1
    assert buckets["8–30 days"]["amount"] == "200.00"
    assert buckets["31–60 days"]["count"] == 1
    assert buckets["31–60 days"]["amount"] == "300.00"
    assert buckets["60+ days"]["count"] == 1
    assert buckets["60+ days"]["amount"] == "500.00"
    assert _sum_overdue_bucket_amounts(data) == Decimal(data["total_overdue_amount"])


@pytest.mark.asyncio
async def test_aging_bucket_boundaries(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Boundary GmbH")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
        original_filename="boundary.csv",
    )

    invoices = [
        ("INV-TODAY", "10.00", date.today()),
        ("INV-YESTERDAY", "20.00", date.today() - timedelta(days=1)),
        ("INV-7", "30.00", date.today() - timedelta(days=7)),
        ("INV-8", "40.00", date.today() - timedelta(days=8)),
        ("INV-30", "50.00", date.today() - timedelta(days=30)),
        ("INV-31", "60.00", date.today() - timedelta(days=31)),
        ("INV-60", "70.00", date.today() - timedelta(days=60)),
        ("INV-61", "80.00", date.today() - timedelta(days=61)),
    ]
    for invoice_number, amount, due_date in invoices:
        await _create_test_invoice(
            db_session,
            test_account.id,
            customer.id,
            import_record.id,
            invoice_number=invoice_number,
            outstanding_amount=amount,
            due_date=due_date,
        )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    buckets = _bucket_map(data)

    assert buckets["Current"]["count"] == 1
    assert buckets["Current"]["amount"] == "10.00"
    assert buckets["1–7 days"]["count"] == 2
    assert buckets["1–7 days"]["amount"] == "50.00"
    assert buckets["8–30 days"]["count"] == 2
    assert buckets["8–30 days"]["amount"] == "90.00"
    assert buckets["31–60 days"]["count"] == 2
    assert buckets["31–60 days"]["amount"] == "130.00"
    assert buckets["60+ days"]["count"] == 1
    assert buckets["60+ days"]["amount"] == "80.00"
    assert data["overdue_today_count"] == 1
    assert data["overdue_today_amount"] == "20.00"


@pytest.mark.asyncio
async def test_aging_reconciliation(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=3)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Recon SARL")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
        original_filename="recon.csv",
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="CUR-RECON",
        outstanding_amount="999.00",
        due_date=date.today() + timedelta(days=5),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-RECON-1",
        outstanding_amount="125.00",
        due_date=date.today() - timedelta(days=3),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="OD-RECON-2",
        outstanding_amount="375.00",
        due_date=date.today() - timedelta(days=45),
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    buckets = _bucket_map(data)

    assert _sum_overdue_bucket_amounts(data) == Decimal(data["total_overdue_amount"])
    assert Decimal(data["total_overdue_amount"]) == Decimal("500.00")
    assert Decimal(buckets["Current"]["amount"]) == Decimal("999.00")
    assert Decimal(buckets["Current"]["amount"]) != Decimal(data["total_overdue_amount"])


@pytest.mark.asyncio
async def test_overdue_today_uses_live_date_math(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(minutes=30)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Live Date SAS")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    invoice = await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="LIVE-001",
        outstanding_amount="250.00",
        due_date=date.today() - timedelta(days=1),
    )
    invoice.days_overdue = 999
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["overdue_today_count"] == 1
    assert data["overdue_today_amount"] == "250.00"


@pytest.mark.asyncio
async def test_top_exposure_correct_customer(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=4)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer_a = await _create_test_customer(db_session, test_account.id, name="Alpha BV")
    customer_b = await _create_test_customer(db_session, test_account.id, name="Beta SRL")
    customer_c = await _create_test_customer(db_session, test_account.id, name="Gamma Ltd")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_a.id,
        import_record.id,
        invoice_number="A-001",
        outstanding_amount="300.00",
        due_date=date.today() - timedelta(days=10),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_a.id,
        import_record.id,
        invoice_number="A-002",
        outstanding_amount="200.00",
        due_date=date.today() - timedelta(days=18),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_b.id,
        import_record.id,
        invoice_number="B-001",
        outstanding_amount="700.00",
        due_date=date.today() - timedelta(days=40),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_b.id,
        import_record.id,
        invoice_number="B-002",
        outstanding_amount="350.00",
        due_date=date.today() - timedelta(days=7),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_c.id,
        import_record.id,
        invoice_number="C-001",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=3),
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    top_exposure = response.json()["top_exposure"]
    assert top_exposure is not None
    assert top_exposure["customer_name"] == "Beta SRL"
    assert top_exposure["total_overdue"] == "1050.00"
    assert top_exposure["overdue_invoice_count"] == 2
    assert top_exposure["oldest_overdue_days"] == 40


@pytest.mark.asyncio
async def test_top_exposure_null_when_no_overdue(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Future SA")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="FUT-001",
        outstanding_amount="120.00",
        due_date=date.today(),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="FUT-002",
        outstanding_amount="220.00",
        due_date=date.today() + timedelta(days=10),
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["top_exposure"] is None
    assert data["total_overdue_count"] == 0


@pytest.mark.asyncio
async def test_possibly_paid_included_in_total_overdue(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Subset SAS")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    for invoice_number, amount, status in [
        ("OPEN-001", "1000.00", "open"),
        ("OPEN-002", "1000.00", "open"),
        ("PP-001", "500.00", "possibly_paid"),
    ]:
        await _create_test_invoice(
            db_session,
            test_account.id,
            customer.id,
            import_record.id,
            invoice_number=invoice_number,
            outstanding_amount=amount,
            due_date=date.today() - timedelta(days=12),
            status=status,
        )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_overdue_amount"] == "2500.00"
    assert data["total_overdue_count"] == 3
    assert data["possibly_paid_count"] == 1


@pytest.mark.asyncio
async def test_disputed_count_is_subset(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Dispute GmbH")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    for invoice_number, status in [
        ("OPEN-A", "open"),
        ("OPEN-B", "open"),
        ("DISPUTED-A", "disputed"),
    ]:
        await _create_test_invoice(
            db_session,
            test_account.id,
            customer.id,
            import_record.id,
            invoice_number=invoice_number,
            outstanding_amount="200.00",
            due_date=date.today() - timedelta(days=9),
            status=status,
        )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["disputed_count"] == 1
    assert data["total_overdue_count"] == 3


@pytest.mark.asyncio
async def test_disputed_not_yet_due_excluded_from_count(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    """A disputed invoice with due_date >= today is NOT overdue and must NOT
    count toward disputed_count (which is a subset of total_overdue)."""
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Future Dispute SA")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    # Overdue disputed — should count
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="DISP-OVERDUE",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=5),
        status="disputed",
    )
    # Not-yet-due disputed — must NOT count
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="DISP-FUTURE",
        outstanding_amount="200.00",
        due_date=date.today() + timedelta(days=3),
        status="disputed",
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["disputed_count"] == 1
    assert data["total_overdue_count"] == 1


@pytest.mark.asyncio
async def test_possibly_paid_not_yet_due_excluded_from_count(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    """A possibly_paid invoice with due_date >= today is NOT overdue and must NOT
    count toward possibly_paid_count (which is a subset of total_overdue)."""
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Future PP BV")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    # Overdue possibly_paid — should count
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="PP-OVERDUE",
        outstanding_amount="150.00",
        due_date=date.today() - timedelta(days=10),
        status="possibly_paid",
    )
    # Not-yet-due possibly_paid — must NOT count
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="PP-FUTURE",
        outstanding_amount="300.00",
        due_date=date.today() + timedelta(days=7),
        status="possibly_paid",
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["possibly_paid_count"] == 1
    assert data["total_overdue_count"] == 1


@pytest.mark.asyncio
async def test_account_isolation(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
    test_user: User,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer_a = await _create_test_customer(db_session, test_account.id, name="Account A")
    import_a = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
        original_filename="a.csv",
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer_a.id,
        import_a.id,
        invoice_number="A-ONLY",
        outstanding_amount="150.00",
        due_date=date.today() - timedelta(days=5),
    )

    second_account = Account(
        id=uuid.uuid4(),
        company_name="Other Company SRL",
        currency="EUR",
        timezone="Europe/Paris",
        language="en",
        first_import_at=confirmed_at,
        last_import_at=confirmed_at,
    )
    db_session.add(second_account)
    await db_session.flush()

    second_user = User(
        id=uuid.uuid4(),
        account_id=second_account.id,
        email="second@example.com",
        hashed_password=hash_password("password123"),
    )
    db_session.add(second_user)
    await db_session.flush()

    customer_b = await _create_test_customer(db_session, second_account.id, name="Account B")
    import_b = await _create_test_import(
        db_session,
        second_account.id,
        confirmed_at=confirmed_at,
        original_filename="b.csv",
    )
    await _create_test_invoice(
        db_session,
        second_account.id,
        customer_b.id,
        import_b.id,
        invoice_number="B-ONLY",
        outstanding_amount="999.00",
        due_date=date.today() - timedelta(days=10),
    )
    await db_session.commit()

    second_auth_headers = {
        "Authorization": f"Bearer {create_access_token({'sub': str(second_user.id)})}"
    }

    response_a = await test_client.get("/dashboard", headers=auth_headers)
    response_b = await test_client.get("/dashboard", headers=second_auth_headers)

    assert response_a.status_code == 200
    assert response_a.json()["total_overdue_amount"] == "150.00"
    assert response_a.json()["total_overdue_count"] == 1
    assert response_b.status_code == 200
    assert response_b.json()["total_overdue_amount"] == "999.00"
    assert response_b.json()["total_overdue_count"] == 1


@pytest.mark.asyncio
async def test_soft_deleted_excluded(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Soft Delete NV")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="KEEP-001",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=4),
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="DROP-001",
        outstanding_amount="200.00",
        due_date=date.today() - timedelta(days=4),
        deleted_at=datetime.now(timezone.utc),
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_overdue_count"] == 1
    assert data["total_overdue_amount"] == "100.00"


@pytest.mark.asyncio
async def test_is_data_stale_true(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    test_account.last_import_at = datetime.now(timezone.utc) - timedelta(hours=25)
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_data_stale"] is True


@pytest.mark.asyncio
async def test_is_data_stale_false(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    test_account.last_import_at = datetime.now(timezone.utc) - timedelta(hours=23)
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["is_data_stale"] is False


@pytest.mark.asyncio
async def test_recent_changes_filtered(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Recent Filter SAS")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )
    invoice = await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="RC-001",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=5),
    )

    now = datetime.now(timezone.utc)
    await _create_test_activity(
        db_session,
        test_account.id,
        action_type="import_committed",
        import_id=import_record.id,
        details={
            "filename": "fresh.csv",
            "invoices_created": 2,
            "invoices_updated": 1,
        },
        created_at=now,
    )
    await _create_test_activity(
        db_session,
        test_account.id,
        action_type="invoice_updated",
        invoice_id=invoice.id,
        customer_id=customer.id,
        details={"changes": {"notes": {"before": None, "after": "memo"}}},
        created_at=now - timedelta(minutes=1),
    )
    await _create_test_activity(
        db_session,
        test_account.id,
        action_type="note_added",
        invoice_id=invoice.id,
        customer_id=customer.id,
        details={"message": "ignore me"},
        created_at=now - timedelta(minutes=2),
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    recent_changes = response.json()["recent_changes"]
    assert len(recent_changes) == 1
    assert recent_changes[0]["action_type"] == "import_committed"


@pytest.mark.asyncio
async def test_recent_changes_descriptions(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_activity(
        db_session,
        test_account.id,
        action_type="import_committed",
        import_id=import_record.id,
        details={
            "filename": "march-aging.csv",
            "invoices_created": 4,
            "invoices_updated": 2,
        },
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    description = response.json()["recent_changes"][0]["description"]
    assert "march-aging.csv" in description
    assert "created" in description


@pytest.mark.asyncio
async def test_last_import(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    older_confirmed_at = datetime.now(timezone.utc) - timedelta(days=2)
    newer_confirmed_at = datetime.now(timezone.utc) - timedelta(hours=6)
    test_account.first_import_at = older_confirmed_at
    test_account.last_import_at = newer_confirmed_at

    await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=older_confirmed_at,
        original_filename="old.csv",
        invoices_created=1,
        invoices_updated=0,
        invoices_disappeared=0,
    )
    await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=newer_confirmed_at,
        original_filename="new.csv",
        invoices_created=3,
        invoices_updated=2,
        invoices_disappeared=1,
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    last_import = response.json()["last_import"]
    assert last_import is not None
    assert last_import["original_filename"] == "new.csv"
    assert last_import["invoices_created"] == 3
    assert last_import["invoices_updated"] == 2
    assert last_import["invoices_disappeared"] == 1


@pytest.mark.asyncio
async def test_recovered_and_closed_excluded(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Terminal BV")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="REC-001",
        outstanding_amount="100.00",
        due_date=date.today() - timedelta(days=20),
        status="recovered",
    )
    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="CLO-001",
        outstanding_amount="200.00",
        due_date=date.today() - timedelta(days=20),
        status="closed",
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total_overdue_count"] == 0
    assert data["total_overdue_amount"] == "0.00"
    assert all(bucket["count"] == 0 for bucket in data["aging_buckets"])


@pytest.mark.asyncio
async def test_current_bucket_includes_not_yet_due(
    test_client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
    test_account: Account,
):
    confirmed_at = datetime.now(timezone.utc) - timedelta(hours=2)
    test_account.first_import_at = confirmed_at
    test_account.last_import_at = confirmed_at
    customer = await _create_test_customer(db_session, test_account.id, name="Current NV")
    import_record = await _create_test_import(
        db_session,
        test_account.id,
        confirmed_at=confirmed_at,
    )

    await _create_test_invoice(
        db_session,
        test_account.id,
        customer.id,
        import_record.id,
        invoice_number="CUR-ONLY",
        outstanding_amount="333.00",
        due_date=date.today() + timedelta(days=1),
        status="open",
    )
    await db_session.commit()

    response = await test_client.get("/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    buckets = _bucket_map(data)
    assert buckets["Current"]["count"] == 1
    assert buckets["Current"]["amount"] == "333.00"
    assert data["total_overdue_count"] == 0
