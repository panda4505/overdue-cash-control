"""Dashboard endpoint with the current overdue picture."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.account import Account
from app.models.activity import Activity
from app.models.customer import Customer
from app.models.import_record import ImportRecord
from app.models.invoice import Invoice
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTIVE_OVERDUE_STATUSES = (
    "open",
    "promised",
    "disputed",
    "paused",
    "escalated",
    "possibly_paid",
)
NON_TERMINAL_STATUSES = (
    "open",
    "promised",
    "disputed",
    "paused",
    "escalated",
    "possibly_paid",
)
OPERATOR_RELEVANT_ACTION_TYPES = (
    "import_committed",
    "invoice_disappeared",
    "anomaly_flagged",
    "customer_merged",
    "invoice_updated",
)
BUCKET_DEFINITIONS = [
    {"label": "Current", "min_days": 0, "max_days": 0, "is_overdue": False},
    {"label": "1–7 days", "min_days": 1, "max_days": 7, "is_overdue": True},
    {"label": "8–30 days", "min_days": 8, "max_days": 30, "is_overdue": True},
    {"label": "31–60 days", "min_days": 31, "max_days": 60, "is_overdue": True},
    {"label": "60+ days", "min_days": 61, "max_days": None, "is_overdue": True},
]
MEANINGFUL_CHANGE_KEYS = {"outstanding_amount", "due_date", "status"}
ZERO = Decimal("0.00")


class AgingBucketResponse(BaseModel):
    label: str
    min_days: int
    max_days: int | None
    count: int
    amount: str
    is_overdue: bool


class TopExposureResponse(BaseModel):
    customer_name: str
    customer_id: UUID
    total_overdue: str
    overdue_invoice_count: int
    oldest_overdue_days: int


class RecentChangeResponse(BaseModel):
    id: UUID
    action_type: str
    description: str
    invoice_number: str | None
    customer_name: str | None
    created_at: datetime


class LastImportResponse(BaseModel):
    id: UUID
    confirmed_at: datetime
    original_filename: str
    invoices_created: int
    invoices_updated: int
    invoices_disappeared: int
    invoices_unchanged: int
    method: str


class DashboardResponse(BaseModel):
    total_overdue_amount: str
    total_overdue_count: int
    overdue_today_count: int
    overdue_today_amount: str
    disputed_count: int
    possibly_paid_count: int
    aging_buckets: list[AgingBucketResponse]
    top_exposure: TopExposureResponse | None
    recent_changes: list[RecentChangeResponse]
    last_import: LastImportResponse | None
    is_data_stale: bool
    currency: str
    first_import_at: datetime | None


def _decimal(value: Decimal | int | float | str | None) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _fmt(amount: Decimal | int | float | str | None) -> str:
    return f"{_decimal(amount).quantize(Decimal('0.01')):.2f}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_invoice_change_summary(changes: dict) -> str | None:
    parts: list[str] = []

    balance_change = changes.get("outstanding_amount")
    if isinstance(balance_change, dict):
        parts.append(
            f"balance {_fmt(balance_change.get('before'))} -> {_fmt(balance_change.get('after'))}"
        )

    due_date_change = changes.get("due_date")
    if isinstance(due_date_change, dict):
        parts.append(
            f"due date {due_date_change.get('before')} -> {due_date_change.get('after')}"
        )

    status_change = changes.get("status")
    if isinstance(status_change, dict):
        parts.append(
            f"status {status_change.get('before')} -> {status_change.get('after')}"
        )

    return ", ".join(parts) if parts else None


def _build_activity_description(
    action_type: str,
    details: dict | None,
    invoice_number: str | None,
    customer_name: str | None,
) -> str | None:
    details = details if isinstance(details, dict) else None

    if action_type == "import_committed":
        filename = str(details.get("filename") or "import") if details else "import"
        invoices_created = int(details.get("invoices_created", 0)) if details else 0
        invoices_updated = int(details.get("invoices_updated", 0)) if details else 0
        return (
            f"Import: {filename} - "
            f"{invoices_created} created, {invoices_updated} updated"
        )

    if action_type == "invoice_updated":
        changes = details.get("changes") if details else None
        if not isinstance(changes, dict):
            return None

        if not any(key in MEANINGFUL_CHANGE_KEYS for key in changes):
            return None

        change_summary = _build_invoice_change_summary(changes)
        if change_summary is None:
            return None

        if invoice_number:
            return f"Invoice {invoice_number} updated - {change_summary}"
        return f"Invoice updated - {change_summary}"

    if action_type == "invoice_disappeared":
        resolved_invoice_number = (
            str(details.get("invoice_number"))
            if details and details.get("invoice_number")
            else invoice_number
        )
        if resolved_invoice_number and customer_name:
            return f"Invoice {resolved_invoice_number} disappeared ({customer_name})"
        if resolved_invoice_number:
            return f"Invoice {resolved_invoice_number} disappeared"
        return "Invoice disappeared"

    if action_type == "anomaly_flagged":
        anomaly_type = str(details.get("anomaly_type") or "unknown") if details else "unknown"
        if invoice_number:
            return f"Anomaly: {anomaly_type} - {invoice_number}"
        return f"Anomaly: {anomaly_type}"

    if action_type == "customer_merged":
        merged_variant = str(details.get("merged_variant") or "Customer") if details else "Customer"
        merged_into = (
            str(details.get("merged_into_name") or customer_name or "customer")
            if details
            else str(customer_name or "customer")
        )
        return f"{merged_variant} merged into {merged_into}"

    return None


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardResponse:
    account_id = current_user.account_id
    today = date.today()
    yesterday = today - timedelta(days=1)
    overdue_days_expr = func.current_date() - Invoice.due_date

    account_result = await db.execute(select(Account).where(Account.id == account_id))
    account = account_result.scalar_one()

    overdue_invoice_filters = (
        Invoice.account_id == account_id,
        Invoice.deleted_at.is_(None),
        Invoice.due_date < today,
        Invoice.status.in_(ACTIVE_OVERDUE_STATUSES),
    )

    total_overdue_result = await db.execute(
        select(
            func.coalesce(func.sum(Invoice.outstanding_amount), ZERO),
            func.count(Invoice.id),
        ).where(*overdue_invoice_filters)
    )
    total_overdue_amount, total_overdue_count = total_overdue_result.one()

    overdue_today_result = await db.execute(
        select(
            func.coalesce(func.sum(Invoice.outstanding_amount), ZERO),
            func.count(Invoice.id),
        ).where(
            Invoice.account_id == account_id,
            Invoice.deleted_at.is_(None),
            Invoice.due_date == yesterday,
            Invoice.status.in_(ACTIVE_OVERDUE_STATUSES),
        )
    )
    overdue_today_amount, overdue_today_count = overdue_today_result.one()

    disputed_count = await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.account_id == account_id,
            Invoice.deleted_at.is_(None),
            Invoice.due_date < today,
            Invoice.status == "disputed",
        )
    )
    possibly_paid_count = await db.scalar(
        select(func.count(Invoice.id)).where(
            Invoice.account_id == account_id,
            Invoice.deleted_at.is_(None),
            Invoice.due_date < today,
            Invoice.status == "possibly_paid",
        )
    )

    aging_bucket_case = case(
        (Invoice.due_date >= func.current_date(), 0),
        (overdue_days_expr.between(1, 7), 1),
        (overdue_days_expr.between(8, 30), 2),
        (overdue_days_expr.between(31, 60), 3),
        (overdue_days_expr > 60, 4),
        else_=0,
    ).label("bucket")

    aging_result = await db.execute(
        select(
            aging_bucket_case,
            func.count(Invoice.id),
            func.coalesce(func.sum(Invoice.outstanding_amount), ZERO),
        )
        .where(
            Invoice.account_id == account_id,
            Invoice.deleted_at.is_(None),
            Invoice.status.in_(NON_TERMINAL_STATUSES),
        )
        .group_by(aging_bucket_case)
    )
    aging_by_bucket = {
        bucket: {"count": count, "amount": _decimal(amount)}
        for bucket, count, amount in aging_result.all()
    }

    aging_buckets = [
        AgingBucketResponse(
            label=definition["label"],
            min_days=definition["min_days"],
            max_days=definition["max_days"],
            count=int(aging_by_bucket.get(index, {}).get("count", 0)),
            amount=_fmt(aging_by_bucket.get(index, {}).get("amount", ZERO)),
            is_overdue=bool(definition["is_overdue"]),
        )
        for index, definition in enumerate(BUCKET_DEFINITIONS)
    ]

    overdue_total = func.sum(Invoice.outstanding_amount).label("total")
    overdue_count = func.count(Invoice.id).label("cnt")
    oldest_overdue_days = func.max(overdue_days_expr).label("oldest_days")

    top_exposure_subquery = (
        select(
            Invoice.customer_id.label("customer_id"),
            overdue_total,
            overdue_count,
            oldest_overdue_days,
        )
        .select_from(Invoice)
        .join(
            Customer,
            and_(
                Customer.id == Invoice.customer_id,
                Customer.account_id == account_id,
                Customer.deleted_at.is_(None),
            ),
        )
        .where(*overdue_invoice_filters, Invoice.customer_id.is_not(None))
        .group_by(Invoice.customer_id)
        .order_by(overdue_total.desc())
        .limit(1)
        .subquery()
    )

    top_exposure_result = await db.execute(
        select(
            Customer.id,
            Customer.name,
            top_exposure_subquery.c.total,
            top_exposure_subquery.c.cnt,
            top_exposure_subquery.c.oldest_days,
        ).join(top_exposure_subquery, Customer.id == top_exposure_subquery.c.customer_id)
    )
    top_exposure_row = top_exposure_result.first()
    top_exposure = None
    if top_exposure_row is not None:
        top_exposure = TopExposureResponse(
            customer_id=top_exposure_row[0],
            customer_name=top_exposure_row[1],
            total_overdue=_fmt(top_exposure_row[2]),
            overdue_invoice_count=int(top_exposure_row[3]),
            oldest_overdue_days=int(top_exposure_row[4]),
        )

    recent_changes_result = await db.execute(
        select(
            Activity,
            Invoice.invoice_number,
            Customer.name.label("customer_name"),
        )
        .select_from(Activity)
        .outerjoin(
            Invoice,
            and_(
                Activity.invoice_id == Invoice.id,
                Invoice.deleted_at.is_(None),
            ),
        )
        .outerjoin(
            Customer,
            and_(
                Activity.customer_id == Customer.id,
                Customer.deleted_at.is_(None),
            ),
        )
        .where(
            Activity.account_id == account_id,
            Activity.action_type.in_(OPERATOR_RELEVANT_ACTION_TYPES),
        )
        .order_by(Activity.created_at.desc())
        .limit(50)
    )

    recent_changes: list[RecentChangeResponse] = []
    for activity, invoice_number, customer_name in recent_changes_result.all():
        description = _build_activity_description(
            action_type=activity.action_type,
            details=activity.details if isinstance(activity.details, dict) else None,
            invoice_number=invoice_number,
            customer_name=customer_name,
        )
        if description is None:
            continue

        recent_changes.append(
            RecentChangeResponse(
                id=activity.id,
                action_type=activity.action_type,
                description=description,
                invoice_number=invoice_number,
                customer_name=customer_name,
                created_at=activity.created_at,
            )
        )
        if len(recent_changes) == 15:
            break

    last_import_result = await db.execute(
        select(ImportRecord)
        .where(
            ImportRecord.account_id == account_id,
            ImportRecord.status == "confirmed",
        )
        .order_by(ImportRecord.confirmed_at.desc())
        .limit(1)
    )
    last_import_record = last_import_result.scalar_one_or_none()
    last_import = None
    if last_import_record is not None and last_import_record.confirmed_at is not None:
        last_import = LastImportResponse(
            id=last_import_record.id,
            confirmed_at=last_import_record.confirmed_at,
            original_filename=last_import_record.original_filename,
            invoices_created=last_import_record.invoices_created,
            invoices_updated=last_import_record.invoices_updated,
            invoices_disappeared=last_import_record.invoices_disappeared,
            invoices_unchanged=last_import_record.invoices_unchanged,
            method=last_import_record.method,
        )

    is_data_stale = account.last_import_at is None or (
        datetime.now(timezone.utc) - _as_utc(account.last_import_at)
        > timedelta(hours=24)
    )

    return DashboardResponse(
        total_overdue_amount=_fmt(total_overdue_amount),
        total_overdue_count=int(total_overdue_count),
        overdue_today_count=int(overdue_today_count),
        overdue_today_amount=_fmt(overdue_today_amount),
        disputed_count=int(disputed_count or 0),
        possibly_paid_count=int(possibly_paid_count or 0),
        aging_buckets=aging_buckets,
        top_exposure=top_exposure,
        recent_changes=recent_changes,
        last_import=last_import,
        is_data_stale=is_data_stale,
        currency=account.currency,
        first_import_at=account.first_import_at,
    )
