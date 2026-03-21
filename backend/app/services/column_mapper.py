"""Column mapper for parsed receivables files."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from app.services.file_parser import ParseResult
from app.services.llm_client import llm_complete


# --- Field tiers ---

# Core fields: stored in the database (Invoice, Customer models)
CORE_FIELDS: dict[str, dict[str, Any]] = {
    "invoice_number": {"required": True, "description": "Invoice number or reference"},
    "customer_name": {"required": True, "description": "Customer/debtor/client company name"},
    "due_date": {"required": True, "description": "Payment due date"},
    "outstanding_amount": {
        "required": True,
        "description": "Remaining balance owed (amount still unpaid)",
    },
    "gross_amount": {
        "required": False,
        "description": "Original total invoice amount (before payments)",
    },
    "issue_date": {"required": False, "description": "Date the invoice was issued"},
    "currency": {"required": False, "description": "Currency code (EUR, CZK, etc.)"},
    "vat_id": {"required": False, "description": "VAT identification number"},
    "company_id": {"required": False, "description": "Company registration number"},
    "email": {"required": False, "description": "Contact email address"},
    "phone": {"required": False, "description": "Contact phone number"},
    "notes": {"required": False, "description": "Free-text notes or remarks"},
}

# Auxiliary fields: shown in import preview but not stored in v1
AUXILIARY_FIELDS: dict[str, dict[str, Any]] = {
    "status": {"required": False, "description": "Invoice status (open, paid, overdue, etc.)"},
    "contact_name": {"required": False, "description": "Contact person name"},
}

# Combined for mapping purposes
CANONICAL_FIELDS: dict[str, dict[str, Any]] = {**CORE_FIELDS, **AUXILIARY_FIELDS}

REQUIRED_FIELDS = [field_name for field_name, meta in CORE_FIELDS.items() if meta["required"]]

EXPECTED_TYPES = {
    "invoice_number": "string",
    "customer_name": "string",
    "due_date": "date",
    "outstanding_amount": "numeric",
    "gross_amount": "numeric",
    "issue_date": "date",
    "currency": "string",
    "vat_id": "string",
    "company_id": "string",
    "email": "string",
    "phone": "string",
    "notes": "string",
    "status": "string",
    "contact_name": "string",
}

_RAW_HEADER_ALIASES: dict[str, list[tuple[str, float]]] = {
    "invoice_number": [
        ("numero de facture", 1.0),
        ("n facture", 0.9),
        ("nº facture", 0.9),
        ("reference facture", 0.9),
        ("ref facture", 0.9),
        ("n de facture", 0.9),
        ("numero fattura", 1.0),
        ("n fattura", 0.9),
        ("rif fattura", 0.9),
        ("riferimento fattura", 0.9),
        ("invoice number", 1.0),
        ("invoice no", 0.9),
        ("invoice ref", 0.9),
        ("inv no", 0.9),
        ("cislo faktury", 1.0),
        ("faktura", 0.9),
        ("c faktury", 0.9),
        ("cislo dokladu", 0.9),
        ("rechnungsnummer", 1.0),
        ("rechnung nr", 0.9),
        ("re nr", 0.9),
        ("belegnummer", 0.9),
        ("numero de factura", 1.0),
        ("n factura", 0.9),
        ("referencia factura", 0.9),
    ],
    "customer_name": [
        ("nom du client", 1.0),
        ("raison sociale", 1.0),
        ("client", 0.9),
        ("societe", 0.9),
        ("nom client", 0.9),
        ("ragione sociale", 1.0),
        ("cliente", 0.9),
        ("denominazione", 0.9),
        ("nome cliente", 0.9),
        ("societa", 0.9),
        ("client name", 1.0),
        ("customer name", 1.0),
        ("customer", 0.9),
        ("company name", 0.9),
        ("debtor", 0.9),
        ("odberatel", 1.0),
        ("firma", 0.9),
        ("nazev firmy", 0.9),
        ("spolecnost", 0.9),
        ("kunde", 0.9),
        ("kundenname", 1.0),
        ("firmenname", 0.9),
        ("nombre del cliente", 1.0),
        ("razon social", 1.0),
        ("empresa", 0.9),
    ],
    "due_date": [
        ("date d echeance", 1.0),
        ("echeance", 0.9),
        ("date limite de paiement", 0.9),
        ("date limite", 0.9),
        ("data scadenza", 1.0),
        ("scadenza", 0.9),
        ("data di scadenza", 1.0),
        ("due date", 1.0),
        ("payment due", 0.9),
        ("date due", 0.9),
        ("datum splatnosti", 1.0),
        ("splatnost", 0.9),
        ("falligkeitsdatum", 1.0),
        ("fallig am", 0.9),
        ("zahlungsziel", 0.9),
        ("fecha de vencimiento", 1.0),
        ("vencimiento", 0.9),
        ("fecha vencimiento", 0.9),
    ],
    "outstanding_amount": [
        ("reste a payer", 1.0),
        ("solde du", 0.9),
        ("montant restant", 0.9),
        ("montant du", 0.9),
        ("importo residuo", 1.0),
        ("residuo", 0.9),
        ("da pagare", 0.9),
        ("importo dovuto", 0.9),
        ("amount due", 1.0),
        ("outstanding amount", 1.0),
        ("amount outstanding", 0.9),
        ("zbyva uhradit", 1.0),
        ("zbyva", 0.9),
        ("nedoplatek", 0.9),
        ("dluzna castka", 0.9),
        ("offener betrag", 1.0),
        ("restbetrag", 0.9),
        ("ausstehend", 0.9),
        ("noch zu zahlen", 0.9),
        ("importe pendiente", 1.0),
        ("pendiente", 0.9),
        ("saldo pendiente", 0.9),
        ("importe adeudado", 0.9),
    ],
    "gross_amount": [
        ("montant ttc", 1.0),
        ("total ttc", 0.9),
        ("montant total", 0.9),
        ("importo lordo", 1.0),
        ("importo totale", 0.9),
        ("totale fattura", 0.9),
        ("total amount", 1.0),
        ("gross amount", 1.0),
        ("invoice amount", 0.9),
        ("invoice total", 0.9),
        ("celkem s dph", 1.0),
        ("celkova castka", 0.9),
        ("castka", 0.9),
        ("celkem", 0.9),
        ("bruttobetrag", 1.0),
        ("gesamtbetrag", 0.9),
        ("rechnungsbetrag", 0.9),
        ("importe total", 1.0),
        ("importe bruto", 0.9),
    ],
    "issue_date": [
        ("date d emission", 1.0),
        ("date de facture", 0.9),
        ("date facture", 0.9),
        ("data emissione", 1.0),
        ("data fattura", 0.9),
        ("data di emissione", 1.0),
        ("issue date", 1.0),
        ("invoice date", 0.9),
        ("date issued", 0.9),
        ("datum vystaveni", 1.0),
        ("vystaveno", 0.9),
        ("rechnungsdatum", 1.0),
        ("ausstellungsdatum", 0.9),
        ("fecha de emision", 1.0),
        ("fecha factura", 0.9),
    ],
    "currency": [
        ("devise", 1.0),
        ("monnaie", 0.9),
        ("valuta", 1.0),
        ("divisa", 0.9),
        ("currency", 1.0),
        ("mena", 1.0),
        ("wahrung", 1.0),
        ("moneda", 0.9),
    ],
    "vat_id": [
        ("tva intracommunautaire", 1.0),
        ("numero tva", 0.9),
        ("n tva", 0.9),
        ("partita iva", 1.0),
        ("p iva", 0.9),
        ("codice iva", 0.9),
        ("vat id", 1.0),
        ("vat number", 0.9),
        ("tax id", 0.9),
        ("dic", 0.9),
        ("ust idnr", 0.9),
        ("ust id", 0.9),
        ("umsatzsteuer id", 0.9),
        ("nif", 0.9),
        ("cif", 0.9),
    ],
    "company_id": [
        ("siret", 1.0),
        ("siren", 0.9),
        ("n siret", 0.9),
        ("numero siret", 0.9),
        ("codice fiscale", 1.0),
        ("registro imprese", 0.9),
        ("company id", 1.0),
        ("registration number", 0.9),
        ("company number", 0.9),
        ("reg no", 0.9),
        ("ico", 0.9),
        ("ic", 0.9),
        ("handelsregisternummer", 0.9),
        ("hrb", 0.9),
        ("numero de registro", 0.9),
    ],
    "email": [
        ("email", 1.0),
        ("e mail", 1.0),
        ("courriel", 0.9),
        ("email client", 1.0),
        ("client email", 1.0),
        ("posta elettronica", 0.9),
        ("correo electronico", 0.9),
    ],
    "phone": [
        ("phone", 1.0),
        ("telephone", 0.9),
        ("telefon", 0.9),
        ("telefono", 0.9),
        ("tel", 0.9),
        ("phone number", 1.0),
        ("numero de telephone", 0.9),
    ],
    "status": [
        ("status", 1.0),
        ("statut", 1.0),
        ("stato", 1.0),
        ("stav", 0.9),
        ("estado", 0.9),
        ("etat", 0.9),
    ],
    "notes": [
        ("notes", 1.0),
        ("note", 0.9),
        ("remarks", 0.9),
        ("comments", 0.9),
        ("poznamka", 0.9),
        ("osservazioni", 0.9),
        ("remarques", 0.9),
        ("bemerkungen", 0.9),
        ("observaciones", 0.9),
    ],
    "contact_name": [
        ("kontakt", 0.9),
        ("contact name", 1.0),
        ("nom du contact", 0.9),
        ("referente", 0.9),
        ("contatto", 0.9),
        ("persona de contacto", 0.9),
    ],
}


@dataclass
class ColumnMapping:
    """A single source-column -> product-field mapping."""

    source_column: str
    target_field: str
    confidence: float
    method: str
    tier: str = "core"


@dataclass
class MappingConflict:
    """Records when two source columns competed for the same target field."""

    target_field: str
    winner: str
    loser: str
    winner_confidence: float
    loser_confidence: float


@dataclass
class MappingResult:
    """Output of the column mapper."""

    success: bool
    mappings: list[ColumnMapping] = field(default_factory=list)
    unmapped_source_columns: list[str] = field(default_factory=list)
    unmapped_required_fields: list[str] = field(default_factory=list)
    amount_fallback_active: bool = False
    conflicts: list[MappingConflict] = field(default_factory=list)
    overall_confidence: float = 0.0
    method: str = "deterministic"
    llm_tokens_used: int | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class _Candidate:
    source_column: str
    target_field: str
    confidence: float
    method: str
    order: int
    type_compatible: bool

    def to_mapping(self) -> ColumnMapping:
        return ColumnMapping(
            source_column=self.source_column,
            target_field=self.target_field,
            confidence=self.confidence,
            method=self.method,
            tier=_tier_for_field(self.target_field),
        )


def _normalize_header(text: str) -> str:
    """Normalize a header for dictionary lookup."""

    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("°", "").replace("º", "")
    text = re.sub(r"[#/\-.,;:()&'\u2019\xa0]", " ", text)
    text = " ".join(text.split())
    return text


def _build_header_dictionary() -> dict[str, tuple[str, float]]:
    header_dictionary: dict[str, tuple[str, float]] = {}
    for target_field, aliases in _RAW_HEADER_ALIASES.items():
        for alias, confidence in aliases:
            normalized = _normalize_header(alias)
            existing = header_dictionary.get(normalized)
            if existing is None or existing[0] == target_field and confidence > existing[1]:
                header_dictionary[normalized] = (target_field, confidence)
            elif existing[0] != target_field and confidence > existing[1]:
                header_dictionary[normalized] = (target_field, confidence)
    return header_dictionary


HEADER_DICTIONARY: dict[str, tuple[str, float]] = _build_header_dictionary()


def _tier_for_field(target_field: str) -> str:
    return "core" if target_field in CORE_FIELDS else "auxiliary"


def _expected_type_for_field(target_field: str) -> str:
    return EXPECTED_TYPES[target_field]


def _add_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _is_hard_mismatch(expected_type: str, detected_type: str) -> bool:
    return expected_type in {"date", "numeric"} and detected_type != expected_type


def _type_compatible(target_field: str, detected_type: str | None) -> bool:
    if detected_type is None:
        return True
    return detected_type == _expected_type_for_field(target_field)


def _build_candidate(
    *,
    source_column: str,
    target_field: str,
    confidence: float,
    method: str,
    order: int,
    detected_type: str | None,
    warnings: list[str],
    apply_type_penalty: bool,
) -> _Candidate:
    expected_type = _expected_type_for_field(target_field)
    type_compatible = _type_compatible(target_field, detected_type)
    adjusted_confidence = confidence

    if apply_type_penalty and detected_type is not None and not type_compatible:
        if _is_hard_mismatch(expected_type, detected_type):
            adjusted_confidence = 0.3
        else:
            adjusted_confidence = min(max(confidence - 0.3, 0.0), 0.5)
        _add_warning(
            warnings,
            (
                f"Column '{source_column}' is typed as '{detected_type}' but target field "
                f"'{target_field}' expects '{expected_type}'."
            ),
        )

    return _Candidate(
        source_column=source_column,
        target_field=target_field,
        confidence=adjusted_confidence,
        method=method,
        order=order,
        type_compatible=type_compatible,
    )


def _generate_deterministic_candidates(
    *,
    parse_result: ParseResult,
    locked_sources: set[str],
    locked_targets: set[str],
    warnings: list[str],
) -> list[_Candidate]:
    candidates: list[_Candidate] = []

    for order, source_column in enumerate(parse_result.headers):
        if source_column in locked_sources:
            continue

        normalized_header = _normalize_header(source_column)
        detected_type = parse_result.column_types.get(source_column)
        exact_match = HEADER_DICTIONARY.get(normalized_header)

        if exact_match is not None:
            target_field, dictionary_confidence = exact_match
            if target_field in locked_targets:
                continue
            candidates.append(
                _build_candidate(
                    source_column=source_column,
                    target_field=target_field,
                    confidence=dictionary_confidence,
                    method="exact" if dictionary_confidence == 1.0 else "synonym",
                    order=order,
                    detected_type=detected_type,
                    warnings=warnings,
                    apply_type_penalty=True,
                )
            )
            continue

        header_tokens = normalized_header.split()
        if len(header_tokens) < 3:
            continue

        header_token_set = set(header_tokens)
        seen_targets: set[str] = set()

        for dictionary_key, (target_field, _) in HEADER_DICTIONARY.items():
            if target_field in locked_targets or target_field in seen_targets:
                continue

            dictionary_tokens = set(dictionary_key.split())
            if not dictionary_tokens:
                continue

            overlap = header_token_set & dictionary_tokens
            if not overlap:
                continue

            dictionary_overlap = len(overlap) / len(dictionary_tokens)
            header_overlap = len(overlap) / len(header_token_set)
            if dictionary_overlap < 0.6 or header_overlap < 0.6:
                continue

            candidates.append(
                _build_candidate(
                    source_column=source_column,
                    target_field=target_field,
                    confidence=0.7,
                    method="partial",
                    order=order,
                    detected_type=detected_type,
                    warnings=warnings,
                    apply_type_penalty=True,
                )
            )
            seen_targets.add(target_field)

    return candidates


def _is_better_source_candidate(new: _Candidate, current: _Candidate) -> bool:
    return new.confidence > current.confidence


def _is_better_target_candidate(new: _Candidate, current: _Candidate) -> bool:
    if new.type_compatible != current.type_compatible:
        return new.type_compatible
    return new.confidence > current.confidence


def _resolve_candidates(candidates: list[_Candidate]) -> tuple[list[ColumnMapping], list[MappingConflict]]:
    best_by_source: dict[str, _Candidate] = {}
    for candidate in candidates:
        current = best_by_source.get(candidate.source_column)
        if current is None or _is_better_source_candidate(candidate, current):
            best_by_source[candidate.source_column] = candidate

    best_by_target: dict[str, _Candidate] = {}
    conflicts: list[MappingConflict] = []

    for candidate in sorted(best_by_source.values(), key=lambda item: item.order):
        current = best_by_target.get(candidate.target_field)
        if current is None:
            best_by_target[candidate.target_field] = candidate
            continue

        if _is_better_target_candidate(candidate, current):
            best_by_target[candidate.target_field] = candidate
            conflicts.append(
                MappingConflict(
                    target_field=candidate.target_field,
                    winner=candidate.source_column,
                    loser=current.source_column,
                    winner_confidence=candidate.confidence,
                    loser_confidence=current.confidence,
                )
            )
        else:
            conflicts.append(
                MappingConflict(
                    target_field=candidate.target_field,
                    winner=current.source_column,
                    loser=candidate.source_column,
                    winner_confidence=current.confidence,
                    loser_confidence=candidate.confidence,
                )
            )

    mappings = [candidate.to_mapping() for candidate in sorted(best_by_target.values(), key=lambda item: item.order)]
    return mappings, conflicts


def _required_scores(mappings: list[ColumnMapping]) -> tuple[dict[str, float], bool]:
    by_field = {mapping.target_field: mapping for mapping in mappings}
    scores: dict[str, float] = {}
    amount_fallback_active = False

    for field_name in REQUIRED_FIELDS:
        if field_name in by_field:
            scores[field_name] = by_field[field_name].confidence
            continue
        if field_name == "outstanding_amount" and "gross_amount" in by_field:
            amount_fallback_active = True
            scores[field_name] = by_field["gross_amount"].confidence

    return scores, amount_fallback_active


def _unmapped_required_fields(mappings: list[ColumnMapping]) -> tuple[list[str], bool]:
    scores, amount_fallback_active = _required_scores(mappings)
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in scores]
    return missing, amount_fallback_active


def _needs_llm(mappings: list[ColumnMapping]) -> bool:
    required_scores, _ = _required_scores(mappings)
    if any(field_name not in required_scores for field_name in REQUIRED_FIELDS):
        return True
    return any(confidence < 0.6 for confidence in required_scores.values())


def _compute_overall_confidence(mappings: list[ColumnMapping]) -> tuple[float, bool, list[str]]:
    required_scores, amount_fallback_active = _required_scores(mappings)
    missing = [field_name for field_name in REQUIRED_FIELDS if field_name not in required_scores]
    if missing:
        return 0.0, amount_fallback_active, missing
    average = sum(required_scores.values()) / len(REQUIRED_FIELDS)
    return average, amount_fallback_active, []


def _template_has_duplicate_sources(existing_mapping: dict[str, str]) -> bool:
    normalized_sources: set[str] = set()
    for source_column in existing_mapping.values():
        normalized = _normalize_header(source_column)
        if normalized in normalized_sources:
            return True
        normalized_sources.add(normalized)
    return False


def _apply_template(
    *,
    parse_result: ParseResult,
    existing_mapping: dict[str, str],
    warnings: list[str],
) -> tuple[list[ColumnMapping], bool]:
    if _template_has_duplicate_sources(existing_mapping):
        _add_warning(
            warnings,
            "Template assigns the same source column to multiple target fields. Falling back to deterministic matching.",
        )
        return [], False

    normalized_headers = {
        _normalize_header(header): header for header in parse_result.headers
    }

    template_mappings: list[ColumnMapping] = []
    for target_field, source_column in existing_mapping.items():
        if target_field not in CANONICAL_FIELDS:
            _add_warning(
                warnings,
                f"Template target field '{target_field}' is unknown and was ignored.",
            )
            continue

        matched_header = normalized_headers.get(_normalize_header(source_column))
        if matched_header is None:
            _add_warning(
                warnings,
                f"Template expects column '{source_column}' but it was not found in the file",
            )
            continue

        template_mappings.append(
            ColumnMapping(
                source_column=matched_header,
                target_field=target_field,
                confidence=1.0,
                method="template",
                tier=_tier_for_field(target_field),
            )
        )

    required_scores, _ = _required_scores(template_mappings)
    if not required_scores:
        _add_warning(
            warnings,
            "Template did not match any required fields. Falling back to deterministic matching.",
        )
        return [], False

    return template_mappings, True


def _build_system_prompt() -> str:
    return (
        "You are a data mapping assistant for a European accounts receivable system. "
        "Given CSV/Excel column headers and sample data, determine which source columns "
        "correspond to which standard invoice fields. Respond with ONLY a valid JSON object, "
        "no markdown fences, no explanation."
    )


def _stringify_sample_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _build_user_prompt(parse_result: ParseResult) -> str:
    field_lines = []
    for field_name, meta in CANONICAL_FIELDS.items():
        label = "[REQUIRED]" if meta["required"] else "[optional]"
        field_lines.append(f"{field_name}: {meta['description']} {label}")

    type_lines = []
    for header in parse_result.headers:
        detected_type = parse_result.column_types.get(header, "unknown")
        type_lines.append(f"{header} (detected type: {detected_type})")

    sample_lines = []
    if parse_result.dataframe is not None:
        for index, row in enumerate(parse_result.dataframe.head(3).itertuples(index=False, name=None), start=1):
            values = ", ".join(
                f"{header}={_stringify_sample_value(value)}"
                for header, value in zip(parse_result.headers, row, strict=False)
            )
            sample_lines.append(f"Row {index}: {values}")

    if not sample_lines:
        sample_lines.append("Row 1: <no sample data available>")

    return "\n".join(
        [
            "Map these source columns to the standard invoice fields.",
            "",
            "Standard fields:",
            *field_lines,
            "",
            "Source columns and detected types:",
            *type_lines,
            "",
            "Sample data (first 3 rows):",
            *sample_lines,
            "",
            "Respond with ONLY a JSON object:",
            "{",
            '  "Source Column Name": {"field": "target_field_name", "confidence": 0.85},',
            "  ...",
            "}",
            "",
            "Rules:",
            "- Map each source column to at most one target field",
            "- Each target field can only be used once",
            "- Use confidence 0.9+ only for high-certainty matches",
            "- Use confidence 0.5-0.8 for plausible but uncertain matches",
            "- Omit columns that don't match any standard field",
            "- At minimum, try to map: invoice_number, customer_name, due_date, and either outstanding_amount or gross_amount",
        ]
    )


def _strip_json_fences(response_text: str) -> str:
    cleaned = response_text.strip()
    fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return cleaned


def _parse_llm_payload(response_text: str) -> dict[str, Any]:
    cleaned = _strip_json_fences(response_text)
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise
        payload = json.loads(cleaned[start : end + 1])

    if not isinstance(payload, dict):
        raise ValueError("LLM payload is not a JSON object")
    return payload


def _validated_llm_candidates(
    *,
    parse_result: ParseResult,
    payload: dict[str, Any],
    warnings: list[str],
) -> list[_Candidate]:
    header_positions = {header: index for index, header in enumerate(parse_result.headers)}
    best_by_target: dict[str, _Candidate] = {}

    for source_column, raw_mapping in payload.items():
        if source_column not in header_positions:
            _add_warning(
                warnings,
                f"LLM suggested unknown source column '{source_column}' and it was ignored.",
            )
            continue

        if not isinstance(raw_mapping, dict):
            _add_warning(
                warnings,
                f"LLM returned an invalid mapping payload for column '{source_column}'.",
            )
            continue

        target_field = raw_mapping.get("field")
        if target_field not in CANONICAL_FIELDS:
            _add_warning(
                warnings,
                f"LLM suggested unknown target field '{target_field}' for column '{source_column}'.",
            )
            continue

        raw_confidence = raw_mapping.get("confidence")
        if not isinstance(raw_confidence, int | float):
            _add_warning(
                warnings,
                f"LLM returned a non-numeric confidence for column '{source_column}'.",
            )
            continue

        confidence = float(raw_confidence)
        if confidence < 0.0 or confidence > 1.0:
            _add_warning(
                warnings,
                (
                    f"LLM returned out-of-range confidence {confidence} for column "
                    f"'{source_column}'. Clamping into [0.0, 1.0]."
                ),
            )
            confidence = min(max(confidence, 0.0), 1.0)

        candidate = _build_candidate(
            source_column=source_column,
            target_field=target_field,
            confidence=confidence,
            method="llm",
            order=header_positions[source_column],
            detected_type=parse_result.column_types.get(source_column),
            warnings=[],
            apply_type_penalty=False,
        )

        current = best_by_target.get(target_field)
        if current is None or candidate.confidence > current.confidence:
            if current is not None:
                _add_warning(
                    warnings,
                    (
                        f"LLM mapped multiple columns to target field '{target_field}'. "
                        f"Keeping '{source_column}' and discarding '{current.source_column}'."
                    ),
                )
            best_by_target[target_field] = candidate
        else:
            _add_warning(
                warnings,
                (
                    f"LLM mapped multiple columns to target field '{target_field}'. "
                    f"Keeping '{current.source_column}' and discarding '{source_column}'."
                ),
            )

    return list(best_by_target.values())


def _candidate_from_mapping(
    mapping: ColumnMapping,
    header_positions: dict[str, int],
    column_types: dict[str, str],
) -> _Candidate:
    return _Candidate(
        source_column=mapping.source_column,
        target_field=mapping.target_field,
        confidence=mapping.confidence,
        method=mapping.method,
        order=header_positions[mapping.source_column],
        type_compatible=_type_compatible(mapping.target_field, column_types.get(mapping.source_column)),
    )


def _merge_with_llm(
    *,
    parse_result: ParseResult,
    current_mappings: list[ColumnMapping],
    llm_candidates: list[_Candidate],
) -> tuple[list[ColumnMapping], list[MappingConflict]]:
    header_positions = {header: index for index, header in enumerate(parse_result.headers)}
    protected_mappings = [
        mapping
        for mapping in current_mappings
        if mapping.method == "template" or mapping.confidence >= 0.7
    ]
    protected_sources = {mapping.source_column for mapping in protected_mappings}
    protected_targets = {mapping.target_field for mapping in protected_mappings}

    candidate_pool = [
        _candidate_from_mapping(mapping, header_positions, parse_result.column_types)
        for mapping in current_mappings
    ]

    for candidate in llm_candidates:
        if candidate.source_column in protected_sources:
            continue
        if candidate.target_field in protected_targets:
            continue
        candidate_pool.append(candidate)

    return _resolve_candidates(candidate_pool)


def _result_method(mappings: list[ColumnMapping]) -> str:
    if not mappings:
        return "deterministic"

    methods = {mapping.method for mapping in mappings}
    if methods == {"template"}:
        return "template"
    if methods <= {"exact", "synonym", "partial"}:
        return "deterministic"
    if methods == {"llm"}:
        return "llm"
    return "mixed"


def _assemble_result(
    *,
    parse_result: ParseResult,
    mappings: list[ColumnMapping],
    conflicts: list[MappingConflict],
    warnings: list[str],
    error: str | None = None,
) -> MappingResult:
    mappings_by_field = {mapping.target_field: mapping for mapping in mappings}
    overall_confidence, amount_fallback_active, unmapped_required_fields = _compute_overall_confidence(mappings)
    mapped_sources = {mapping.source_column for mapping in mappings}
    unmapped_source_columns = [
        header for header in parse_result.headers if header not in mapped_sources
    ]

    return MappingResult(
        success=True,
        mappings=sorted(
            mappings,
            key=lambda mapping: parse_result.headers.index(mapping.source_column),
        ),
        unmapped_source_columns=unmapped_source_columns,
        unmapped_required_fields=unmapped_required_fields,
        amount_fallback_active=amount_fallback_active,
        conflicts=conflicts,
        overall_confidence=overall_confidence,
        method=_result_method(list(mappings_by_field.values())),
        llm_tokens_used=None,
        warnings=warnings,
        error=error,
    )


async def map_columns(
    parse_result: ParseResult,
    existing_mapping: dict[str, str] | None = None,
) -> MappingResult:
    """Map source headers to canonical invoice fields."""

    try:
        if not parse_result.success or not parse_result.headers:
            return MappingResult(success=False, error="No valid parse result to map")

        warnings = list(parse_result.warnings)
        current_conflicts: list[MappingConflict] = []

        template_mappings: list[ColumnMapping] = []
        template_valid = False
        if existing_mapping:
            template_mappings, template_valid = _apply_template(
                parse_result=parse_result,
                existing_mapping=existing_mapping,
                warnings=warnings,
            )

        if template_valid:
            locked_sources = {mapping.source_column for mapping in template_mappings}
            locked_targets = {mapping.target_field for mapping in template_mappings}
            deterministic_candidates = _generate_deterministic_candidates(
                parse_result=parse_result,
                locked_sources=locked_sources,
                locked_targets=locked_targets,
                warnings=warnings,
            )
            deterministic_mappings, deterministic_conflicts = _resolve_candidates(deterministic_candidates)
            current_mappings = template_mappings + deterministic_mappings
            current_conflicts.extend(deterministic_conflicts)
        else:
            deterministic_candidates = _generate_deterministic_candidates(
                parse_result=parse_result,
                locked_sources=set(),
                locked_targets=set(),
                warnings=warnings,
            )
            current_mappings, deterministic_conflicts = _resolve_candidates(deterministic_candidates)
            current_conflicts.extend(deterministic_conflicts)

        if not _needs_llm(current_mappings):
            return _assemble_result(
                parse_result=parse_result,
                mappings=current_mappings,
                conflicts=current_conflicts,
                warnings=warnings,
            )

        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(parse_result)

        try:
            llm_response = await llm_complete(prompt=user_prompt, system=system_prompt)
        except Exception as exc:
            _add_warning(
                warnings,
                f"LLM fallback failed: {exc}. Mapping based on deterministic matching only.",
            )
            return _assemble_result(
                parse_result=parse_result,
                mappings=current_mappings,
                conflicts=current_conflicts,
                warnings=warnings,
            )

        try:
            payload = _parse_llm_payload(llm_response)
        except Exception:
            _add_warning(
                warnings,
                "LLM returned invalid JSON. Falling back to deterministic matching.",
            )
            return _assemble_result(
                parse_result=parse_result,
                mappings=current_mappings,
                conflicts=current_conflicts,
                warnings=warnings,
            )

        llm_candidates = _validated_llm_candidates(
            parse_result=parse_result,
            payload=payload,
            warnings=warnings,
        )
        merged_mappings, merge_conflicts = _merge_with_llm(
            parse_result=parse_result,
            current_mappings=current_mappings,
            llm_candidates=llm_candidates,
        )

        return _assemble_result(
            parse_result=parse_result,
            mappings=merged_mappings,
            conflicts=current_conflicts + merge_conflicts,
            warnings=warnings,
        )
    except Exception as exc:  # pragma: no cover - safety net
        return MappingResult(success=False, error=str(exc))
