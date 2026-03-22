"""Import lifecycle endpoints: upload, save template, confirm."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.account import Account
from app.models.import_record import ImportRecord
from app.models.user import User
from app.services.file_parser import parse_file
from app.services.import_commit import confirm_import, create_pending_import
from app.services.template_service import (
    find_matching_template,
    save_template,
    template_to_dict,
)

router = APIRouter(prefix="/accounts", tags=["imports"])


class ConfirmImportRequest(BaseModel):
    """Request body for confirming an import."""

    mapping: dict[str, str]
    scope_type: Literal["full_snapshot", "partial", "unknown"] = "unknown"
    merge_decisions: dict[str, str] | None = None


class SaveTemplateRequest(BaseModel):
    """Request body for saving a column mapping as a reusable template."""

    name: str
    mapping: dict[str, str]
    scope_type: Literal["full_snapshot", "partial", "unknown"] = "unknown"
    delimiter: str | None = None
    decimal_separator: str | None = None
    thousands_separator: str | None = None
    encoding: str | None = None
    date_format: str | None = None


@router.post("/{account_id}/imports/upload")
async def upload_for_import(
    account_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Upload a file, create a pending import, and return its preview.

    If a saved template matches the file structure, it is auto-applied
    and included in the response as 'applied_template'.
    """

    if current_user.account_id != account_id:
        raise HTTPException(status_code=403, detail="Access denied")

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

    template_mapping: dict[str, str] | None = None
    applied_template_info: dict[str, Any] | None = None

    try:
        parse_result = parse_file(file_bytes, file.filename)
        if parse_result.success and parse_result.headers:
            matching_template = await find_matching_template(
                db=db,
                account_id=account_id,
                file_headers=parse_result.headers,
                delimiter=parse_result.delimiter,
                decimal_separator=parse_result.decimal_separator,
            )
            if matching_template is not None:
                template_mapping = matching_template.column_mapping
                applied_template_info = template_to_dict(matching_template)
                matching_template.times_used = (matching_template.times_used or 0) + 1
    except Exception:
        pass

    result = await create_pending_import(
        db=db,
        account_id=account_id,
        file_bytes=file_bytes,
        filename=file.filename,
        method="upload",
        template_mapping=template_mapping,
    )

    if applied_template_info is not None:
        result["applied_template"] = applied_template_info

    return result


confirm_router = APIRouter(tags=["imports"])


@confirm_router.post("/imports/{import_id}/save-template")
async def save_template_endpoint(
    import_id: uuid.UUID,
    body: SaveTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Save a confirmed column mapping as a reusable template.

    Idempotent: if the import already has a linked template, it is
    updated rather than duplicated.
    """

    import_query = select(ImportRecord).where(ImportRecord.id == import_id)
    import_result = await db.execute(import_query)
    import_record = import_result.scalar_one_or_none()

    if import_record is None:
        raise HTTPException(status_code=404, detail=f"Import {import_id} not found")
    if import_record.account_id != current_user.account_id:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        template = await save_template(
            db=db,
            account_id=current_user.account_id,
            import_id=import_id,
            name=body.name,
            mapping=body.mapping,
            scope_type=body.scope_type,
            delimiter=body.delimiter,
            decimal_separator=body.decimal_separator,
            thousands_separator=body.thousands_separator,
            encoding=body.encoding,
            date_format=body.date_format,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"template": template_to_dict(template)}


@confirm_router.post("/imports/{import_id}/confirm")
async def confirm_import_endpoint(
    import_id: uuid.UUID,
    body: ConfirmImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Confirm a pending import and commit it to the database."""

    import_query = select(ImportRecord).where(ImportRecord.id == import_id)
    import_result = await db.execute(import_query)
    import_record = import_result.scalar_one_or_none()

    if import_record is None:
        raise HTTPException(status_code=404, detail=f"Import {import_id} not found")
    if import_record.account_id != current_user.account_id:
        raise HTTPException(status_code=403, detail="Access denied")

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
