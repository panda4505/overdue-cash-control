"""Invoice number and customer name normalization for matching."""

from __future__ import annotations

import re
import unicodedata

# Legal suffixes to strip from company names — European-first.
# Order matters: longer suffixes first to avoid partial matches.
LEGAL_SUFFIXES: list[str] = [
    # Czech / Slovak
    "spol. s r.o.",
    "s.r.o.",
    "a.s.",
    "k.s.",
    "v.o.s.",
    "sro",
    # German
    "gmbh & co. ohg",
    "gmbh & co. kg",
    "gmbh",
    "e.k.",
    "ag",
    "ohg",
    "kg",
    "gbr",
    "ug",
    # French
    "sarl",
    "eurl",
    "sas",
    "sci",
    "snc",
    "sca",
    "sa",
    # Italian
    "s.r.l.",
    "s.p.a.",
    "s.a.s.",
    "s.n.c.",
    "s.s.",
    "srl",
    "spa",
    # Spanish
    "s.l.u.",
    "s.l.",
    "s.a.",
    "s.c.",
    "sl",
    # English
    "limited",
    "ltd.",
    "ltd",
    "llc",
    "plc",
    "inc.",
    "inc",
    "corp.",
    "corp",
]

_SUFFIX_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(suffix) for suffix in LEGAL_SUFFIXES) + r")\s*$",
    re.IGNORECASE,
)


def normalize_invoice_number(raw: str) -> str:
    """Normalize an invoice number for matching."""

    if not raw:
        return ""

    text = unicodedata.normalize("NFC", raw.strip().lower())
    text = re.sub(r"[\W_]+", "", text, flags=re.UNICODE)
    return text


def normalize_customer_name(raw: str) -> str:
    """Normalize a company name for exact matching."""

    if not raw:
        return ""

    text = unicodedata.normalize("NFC", raw.strip()).lower()
    for _ in range(2):
        text = _SUFFIX_PATTERN.sub("", text).strip()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(" ,.-")
    return text
