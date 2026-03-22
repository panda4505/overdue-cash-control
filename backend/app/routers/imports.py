"""Import lifecycle endpoints: create pending imports and confirm them."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import Account
from app.services.import_commit import confirm_import, create_pending_import

router = APIRouter(prefix="/accounts", tags=["imports"])


class ConfirmImportRequest(BaseModel):
    """Request body for confirming an import."""

    mapping: dict[str, str]
    scope_type: Literal["full_snapshot", "partial", "unknown"] = "unknown"
    merge_decisions: dict[str, str] | None = None
    # Keys: normalized customer name from the file
    # Values: UUID string of existing customer to merge into
    # Only needed for medium-confidence fuzzy matches the user confirmed.
    # Omitted or null = no merges for ambiguous matches.


@router.post("/{account_id}/imports/upload")
async def upload_for_import(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a file, create a pending import, and return its preview."""

    account_query = select(Account).where(Account.id == account_id)
    account_result = await db.execute(account_query)
    if account_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if extension not in {"csv", "tsv", "xlsx"}:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{extension}. Supported: .csv, .tsv, .xlsx",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    return await create_pending_import(
        db=db,
        account_id=account_id,
        file_bytes=file_bytes,
        filename=file.filename,
        method="upload",
    )


confirm_router = APIRouter(tags=["imports"])


@confirm_router.post("/imports/{import_id}/confirm")
async def confirm_import_endpoint(
    import_id: uuid.UUID,
    body: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Confirm a pending import and commit it to the database."""

    try:
        return await confirm_import(
            db=db,
            import_id=import_id,
            confirmed_mapping=body.mapping,
            scope_type=body.scope_type,
            merge_decisions=body.merge_decisions,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail=message) from exc
        if "expected 'pending_preview'" in message:
            raise HTTPException(status_code=409, detail=message) from exc
        raise HTTPException(status_code=400, detail=message) from exc
