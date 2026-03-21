"""Shared file ingestion pipeline used by upload and email entry points."""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.services.column_mapper import MappingResult, map_columns
from app.services.file_parser import parse_file


@dataclass
class IngestionResult:
    """Everything the preview screen needs after parse + map."""

    success: bool
    filename: str
    file_hash: str = ""
    file_size_bytes: int = 0
    encoding: str | None = None
    delimiter: str | None = None
    date_format: str | None = None
    decimal_separator: str | None = None
    thousands_separator: str | None = None
    total_rows: int = 0
    mapping: MappingResult | None = None
    sample_rows: list[dict[str, Any]] = field(default_factory=list)
    sheet_name: str | None = None
    sheet_names: list[str] = field(default_factory=list)
    method: str = "upload"
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def _serialize_value(value: Any) -> Any:
    """Convert a value to a JSON-safe type."""

    if value is None or value == "":
        return None
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, float):
        return value
    return str(value)


async def ingest_file(
    file_bytes: bytes,
    filename: str,
    method: str = "upload",
    existing_template: dict[str, str] | None = None,
) -> IngestionResult:
    """Run the canonical parse -> map -> preview ingestion pipeline."""

    try:
        if not file_bytes:
            return IngestionResult(
                success=False,
                filename=filename,
                method=method,
                error="Empty file",
            )

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        file_size_bytes = len(file_bytes)

        parse_result = parse_file(file_bytes, filename)
        if parse_result.success is False:
            return IngestionResult(
                success=False,
                filename=filename,
                file_hash=file_hash,
                file_size_bytes=file_size_bytes,
                method=method,
                warnings=parse_result.warnings,
                error=parse_result.error,
            )

        mapping_result = await map_columns(
            parse_result,
            existing_mapping=existing_template,
        )

        sample_rows: list[dict[str, Any]] = []
        if parse_result.dataframe is not None:
            for _, row in parse_result.dataframe.head(10).iterrows():
                sample_rows.append(
                    {
                        column: _serialize_value(row[column])
                        for column in parse_result.headers
                    }
                )

        return IngestionResult(
            success=mapping_result.success,
            filename=filename,
            file_hash=file_hash,
            file_size_bytes=file_size_bytes,
            encoding=parse_result.encoding,
            delimiter=parse_result.delimiter,
            date_format=parse_result.date_format,
            decimal_separator=parse_result.decimal_separator,
            thousands_separator=parse_result.thousands_separator,
            total_rows=parse_result.total_rows,
            mapping=mapping_result,
            sample_rows=sample_rows,
            sheet_name=parse_result.sheet_name,
            sheet_names=parse_result.sheet_names,
            method=method,
            warnings=parse_result.warnings
            + [warning for warning in mapping_result.warnings if warning not in parse_result.warnings],
            error=mapping_result.error,
        )
    except Exception as exc:  # pragma: no cover - safety net
        return IngestionResult(
            success=False,
            filename=filename,
            method=method,
            error=str(exc),
        )
