"""Fuzzy customer matching — same-entity resolution only.

Pure logic module. No database imports. Fully unit-testable without Postgres.
Relationship/group intelligence is out of scope — see BUILD_LOG decision #23.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from typing import Any

import jellyfish

HIGH_THRESHOLD = 0.90
LOW_THRESHOLD = 0.70

_COMBINING_MARKS = re.compile(r"[\u0300-\u036f]")


def fold_diacritics(text: str) -> str:
    """Strip diacritics for fuzzy comparison. NOT for storage or display.

    NFD decomposition splits base characters from combining marks.
    Stripping combining marks gives ASCII-approximate form.
    NFC recomposition normalizes the result.

    Examples:
        "société générale" -> "societe generale"
        "ñoño" -> "nono"
        "naïve" -> "naive"
    """

    decomposed = unicodedata.normalize("NFD", text)
    stripped = _COMBINING_MARKS.sub("", decomposed)
    return unicodedata.normalize("NFC", stripped)


@dataclasses.dataclass
class FileCustomer:
    """A unique customer identity extracted from an import file."""

    normalized_name: str
    raw_name: str
    vat_id: str | None = None


@dataclasses.dataclass
class ExistingCustomerInfo:
    """Projection of a DB Customer for matching — no ORM dependency."""

    customer_id: str
    normalized_name: str
    display_name: str
    vat_id: str | None = None
    merge_history: list[dict[str, Any]] | None = None


@dataclasses.dataclass
class MatchResult:
    """One match between a file customer and an existing customer."""

    file_normalized_name: str
    file_raw_name: str
    existing_customer_id: str
    existing_customer_name: str
    score: float
    match_type: str
    confidence: str


@dataclasses.dataclass
class FuzzyMatchResult:
    """Complete fuzzy matching result for an import."""

    auto_merges: list[MatchResult]
    candidates: list[MatchResult]


def find_best_match(
    file_customer: FileCustomer,
    existing_customers: list[ExistingCustomerInfo],
    *,
    high_threshold: float = HIGH_THRESHOLD,
    low_threshold: float = LOW_THRESHOLD,
) -> MatchResult | None:
    """Find the single best match for one file customer. Returns None if no match.

    This is the shared matching function used by both preview and confirm paths.
    It does NOT handle exact normalized-name matches — those are handled upstream.
    """

    existing_normalized_names = {ec.normalized_name for ec in existing_customers}
    if file_customer.normalized_name in existing_normalized_names:
        return None

    for ec in existing_customers:
        if not isinstance(ec.merge_history, list):
            continue
        for entry in ec.merge_history:
            if entry.get("normalized_name") == file_customer.normalized_name:
                return MatchResult(
                    file_normalized_name=file_customer.normalized_name,
                    file_raw_name=file_customer.raw_name,
                    existing_customer_id=ec.customer_id,
                    existing_customer_name=ec.display_name,
                    score=1.0,
                    match_type="merge_history",
                    confidence="high",
                )

    if file_customer.vat_id and file_customer.vat_id.strip():
        file_vat_id = file_customer.vat_id.strip().upper()
        for ec in existing_customers:
            if ec.vat_id and ec.vat_id.strip().upper() == file_vat_id:
                return MatchResult(
                    file_normalized_name=file_customer.normalized_name,
                    file_raw_name=file_customer.raw_name,
                    existing_customer_id=ec.customer_id,
                    existing_customer_name=ec.display_name,
                    score=1.0,
                    match_type="vat_id",
                    confidence="high",
                )

    folded_file_name = fold_diacritics(file_customer.normalized_name)
    best_score = 0.0
    best_customer: ExistingCustomerInfo | None = None
    for ec in existing_customers:
        folded_existing_name = fold_diacritics(ec.normalized_name)
        score = jellyfish.jaro_winkler_similarity(folded_file_name, folded_existing_name)
        if score > best_score:
            best_score = score
            best_customer = ec

    if best_customer is None:
        return None

    if best_score >= high_threshold:
        return MatchResult(
            file_normalized_name=file_customer.normalized_name,
            file_raw_name=file_customer.raw_name,
            existing_customer_id=best_customer.customer_id,
            existing_customer_name=best_customer.display_name,
            score=best_score,
            match_type="name_similarity",
            confidence="high",
        )

    if best_score >= low_threshold:
        return MatchResult(
            file_normalized_name=file_customer.normalized_name,
            file_raw_name=file_customer.raw_name,
            existing_customer_id=best_customer.customer_id,
            existing_customer_name=best_customer.display_name,
            score=best_score,
            match_type="name_similarity",
            confidence="medium",
        )

    return None


def find_fuzzy_matches(
    file_customers: list[FileCustomer],
    existing_customers: list[ExistingCustomerInfo],
    *,
    high_threshold: float = HIGH_THRESHOLD,
    low_threshold: float = LOW_THRESHOLD,
) -> FuzzyMatchResult:
    """Find fuzzy matches for all file customers against existing customers.

    Calls find_best_match for each file customer. Splits results into
    auto_merges (high confidence) and candidates (medium confidence).
    """

    auto_merges: list[MatchResult] = []
    candidates: list[MatchResult] = []

    for file_customer in file_customers:
        match = find_best_match(
            file_customer,
            existing_customers,
            high_threshold=high_threshold,
            low_threshold=low_threshold,
        )
        if match is None:
            continue
        if match.confidence == "high":
            auto_merges.append(match)
        else:
            candidates.append(match)

    return FuzzyMatchResult(auto_merges=auto_merges, candidates=candidates)


def match_result_to_dict(match: MatchResult) -> dict[str, Any]:
    return dataclasses.asdict(match)


def fuzzy_match_result_to_dict(result: FuzzyMatchResult) -> dict[str, Any]:
    return {
        "auto_merges": [match_result_to_dict(match) for match in result.auto_merges],
        "candidates": [match_result_to_dict(match) for match in result.candidates],
    }
