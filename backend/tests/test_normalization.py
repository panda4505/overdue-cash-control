from __future__ import annotations

import pytest

from app.services.normalization import normalize_customer_name, normalize_invoice_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FV-2024/001", "fv2024001"),
        (" INV 001 ", "inv001"),
        ("FA.2024.001", "fa2024001"),
        ("fv2024001", "fv2024001"),
        ("", ""),
        ("Fč-2024/01", "fč202401"),
    ],
)
def test_normalize_invoice_number(raw: str, expected: str):
    assert normalize_invoice_number(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ACME s.r.o.", "acme"),
        ("Müller GmbH", "müller"),
        ("Müller GmbH & Co. KG", "müller"),
        ("Société Générale SAS", "société générale"),
        ("Fiat S.p.A.", "fiat"),
        ("Acme Ltd.", "acme"),
        ("Acme Ltd", "acme"),
        ("Empresa S.L.", "empresa"),
        ("Plain Company", "plain company"),
        ("  ACME   S.R.O.  ", "acme"),
        ("", ""),
        ("Test GMBH", "test"),
        ("Test, Ltd.", "test"),
    ],
)
def test_normalize_customer_name(raw: str, expected: str):
    assert normalize_customer_name(raw) == expected
