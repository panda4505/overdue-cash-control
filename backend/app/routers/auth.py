"""Auth endpoints: register, login, me, update account."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.account import Account
from app.models.user import User
from app.services.auth import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UpdateAccountRequest(BaseModel):
    company_name: str | None = None
    currency: str | None = None
    timezone: str | None = None
    language: str | None = None


def _user_response(user: User, account_id: str) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "account_id": account_id,
    }


def _account_response(account: Account) -> dict:
    return {
        "id": str(account.id),
        "company_name": account.company_name,
        "currency": account.currency,
        "timezone": account.timezone,
        "language": account.language,
        "resend_inbound_address": account.resend_inbound_address,
        "first_import_at": (
            account.first_import_at.isoformat() if account.first_import_at else None
        ),
        "last_import_at": (
            account.last_import_at.isoformat() if account.last_import_at else None
        ),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user and account. Returns JWT token."""

    normalized_email = body.email.strip().lower()

    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters",
        )

    account = Account(
        currency="EUR",
        timezone="Europe/Paris",
        language="en",
    )
    db.add(account)
    await db.flush()

    user = User(
        account_id=account.id,
        email=normalized_email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    await db.refresh(account)

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_response(user, str(account.id)),
    }


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT token."""

    normalized_email = body.email.strip().lower()

    query = select(User).where(User.email == normalized_email)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is disabled",
        )

    token = create_access_token({"sub": str(user.id)})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _user_response(user, str(user.account_id)),
    }


@router.get("/me")
async def me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user and account info."""

    account_query = select(Account).where(Account.id == current_user.account_id)
    account_result = await db.execute(account_query)
    account = account_result.scalar_one()

    return {
        "user": _user_response(current_user, str(account.id)),
        "account": _account_response(account),
    }


@router.patch("/account")
async def update_account(
    body: UpdateAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update account settings. Used during onboarding and settings."""

    account_query = select(Account).where(Account.id == current_user.account_id)
    account_result = await db.execute(account_query)
    account = account_result.scalar_one_or_none()

    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if body.company_name is not None:
        account.company_name = body.company_name
    if body.currency is not None:
        account.currency = body.currency
    if body.timezone is not None:
        account.timezone = body.timezone
    if body.language is not None:
        account.language = body.language

    await db.commit()
    await db.refresh(account)

    return {"account": _account_response(account)}
