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


class TestDotlessSuffixNormalization:
    """Dotless legal suffix variants normalize the same as dotted ones."""

    def test_czech_sro_dotless(self):
        assert normalize_customer_name("Acme SRO") == normalize_customer_name("Acme s.r.o.")

    def test_italian_srl_dotless(self):
        assert normalize_customer_name("Acme SRL") == normalize_customer_name("Acme S.R.L.")

    def test_italian_spa_dotless(self):
        assert normalize_customer_name("Fiat SpA") == normalize_customer_name("Fiat S.p.A.")

    def test_spanish_sl_dotless(self):
        assert normalize_customer_name("Empresa SL") == normalize_customer_name("Empresa S.L.")

    def test_spa_not_stripped_from_middle(self):
        """'spa' suffix must not match inside words."""
        result = normalize_customer_name("Sparrow Industries")
        assert "sparrow" in result
