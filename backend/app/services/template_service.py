"""Template persistence and conservative auto-apply service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.import_record import ImportRecord
from app.models.import_template import ImportTemplate


async def save_template(
    db: AsyncSession,
    account_id: uuid.UUID,
    import_id: uuid.UUID,
    name: str,
    mapping: dict[str, str],
    scope_type: str = "unknown",
    delimiter: str | None = None,
    decimal_separator: str | None = None,
    thousands_separator: str | None = None,
    encoding: str | None = None,
    date_format: str | None = None,
) -> ImportTemplate:
    """Save a confirmed column mapping as a reusable template.

    Idempotent per import: if the import already has a linked template,
    update that template instead of creating a duplicate.
    """

    import_query = select(ImportRecord).where(ImportRecord.id == import_id)
    import_result = await db.execute(import_query)
    import_record = import_result.scalar_one_or_none()

    if import_record is None:
        raise ValueError(f"Import {import_id} not found")
    if import_record.account_id != account_id:
        raise ValueError("Import does not belong to this account")

    if import_record.template_id is not None:
        existing_query = select(ImportTemplate).where(
            ImportTemplate.id == import_record.template_id
        )
        existing_result = await db.execute(existing_query)
        existing_template = existing_result.scalar_one_or_none()
        if existing_template is not None:
            existing_template.name = name
            existing_template.column_mapping = mapping
            existing_template.scope_type = scope_type
            existing_template.delimiter = delimiter
            existing_template.decimal_separator = decimal_separator
            existing_template.thousands_separator = thousands_separator
            existing_template.encoding = encoding
            existing_template.date_format = date_format
            await db.commit()
            await db.refresh(existing_template)
            return existing_template

    template = ImportTemplate(
        account_id=account_id,
        name=name,
        column_mapping=mapping,
        scope_type=scope_type,
        delimiter=delimiter,
        decimal_separator=decimal_separator,
        thousands_separator=thousands_separator,
        encoding=encoding,
        date_format=date_format,
    )
    db.add(template)
    await db.flush()

    import_record.template_id = template.id

    await db.commit()
    await db.refresh(template)

    return template


async def find_matching_template(
    db: AsyncSession,
    account_id: uuid.UUID,
    file_headers: list[str],
    delimiter: str | None = None,
    decimal_separator: str | None = None,
) -> ImportTemplate | None:
    """Find a saved template that matches the uploaded file's structure.

    Conservative auto-apply rules:
    1. The normalized set of mapped source columns in the template must EXACTLY
       equal the normalized set of file headers. A file with extra or missing
       columns is a different export shape and should route to the mapping screen.
    2. Delimiter must match (if both non-null)
    3. Decimal separator must match (if both non-null)
    4. Exactly ONE template must match — if zero or multiple, return None

    This is intentionally strict. If real users find it too restrictive,
    we can loosen with evidence later.
    """

    query = select(ImportTemplate).where(ImportTemplate.account_id == account_id)
    result = await db.execute(query)
    templates = result.scalars().all()

    if not templates:
        return None

    normalized_file_headers = {h.strip().lower() for h in file_headers}

    candidates: list[ImportTemplate] = []

    for template in templates:
        if not isinstance(template.column_mapping, dict):
            continue

        template_source_columns = set()
        for value in template.column_mapping.values():
            if isinstance(value, str) and value.strip():
                template_source_columns.add(value.strip().lower())

        if not template_source_columns:
            continue

        if template_source_columns != normalized_file_headers:
            continue

        if (
            delimiter is not None
            and template.delimiter is not None
            and delimiter != template.delimiter
        ):
            continue

        if (
            decimal_separator is not None
            and template.decimal_separator is not None
            and decimal_separator != template.decimal_separator
        ):
            continue

        candidates.append(template)

    if len(candidates) == 1:
        return candidates[0]

    return None


def template_to_dict(template: ImportTemplate) -> dict[str, Any]:
    """Serialize an ImportTemplate for API responses."""

    return {
        "id": str(template.id),
        "name": template.name,
        "scope_type": template.scope_type,
        "column_mapping": template.column_mapping,
        "delimiter": template.delimiter,
        "decimal_separator": template.decimal_separator,
        "thousands_separator": template.thousands_separator,
        "encoding": template.encoding,
        "date_format": template.date_format,
        "times_used": template.times_used,
    }
