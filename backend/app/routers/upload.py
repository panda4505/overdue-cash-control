"""Manual file upload endpoint for ingestion previews."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion import IngestionResult, ingest_file

router = APIRouter()


def _serialize_ingestion_result(result: IngestionResult) -> dict[str, Any]:
    """Convert IngestionResult to a JSON-serializable dict."""

    mapping_data = None
    if result.mapping:
        mapping_data = {
            "success": result.mapping.success,
            "mappings": [
                {
                    "source_column": mapping.source_column,
                    "target_field": mapping.target_field,
                    "confidence": mapping.confidence,
                    "method": mapping.method,
                    "tier": mapping.tier,
                }
                for mapping in result.mapping.mappings
            ],
            "unmapped_source_columns": result.mapping.unmapped_source_columns,
            "unmapped_required_fields": result.mapping.unmapped_required_fields,
            "amount_fallback_active": result.mapping.amount_fallback_active,
            "conflicts": [
                {
                    "target_field": conflict.target_field,
                    "winner": conflict.winner,
                    "loser": conflict.loser,
                    "winner_confidence": conflict.winner_confidence,
                    "loser_confidence": conflict.loser_confidence,
                }
                for conflict in result.mapping.conflicts
            ],
            "overall_confidence": result.mapping.overall_confidence,
            "method": result.mapping.method,
        }

    return {
        "success": result.success,
        "filename": result.filename,
        "file_hash": result.file_hash,
        "file_size_bytes": result.file_size_bytes,
        "encoding": result.encoding,
        "delimiter": result.delimiter,
        "date_format": result.date_format,
        "decimal_separator": result.decimal_separator,
        "thousands_separator": result.thousands_separator,
        "total_rows": result.total_rows,
        "mapping": mapping_data,
        "sample_rows": result.sample_rows,
        "sheet_name": result.sheet_name,
        "sheet_names": result.sheet_names,
        "method": result.method,
        "warnings": result.warnings,
        "error": result.error,
    }


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)) -> dict[str, Any]:
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
    return _serialize_ingestion_result(result)
