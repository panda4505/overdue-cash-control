"""Manual file upload endpoint for ingestion previews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies import get_current_user
from app.models.user import User
from app.services.ingestion import ingest_file

router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Accept a CSV/XLSX file upload and return parsed + mapped preview data."""

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

    result = await ingest_file(
        file_bytes=file_bytes,
        filename=file.filename,
        method="upload",
    )
    return result.to_dict()
