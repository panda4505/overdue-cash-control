import datetime
from pathlib import Path

import pytest

from app.services.file_parser import parse_file

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


class TestPohodaCSV:
    """Semicolon-delimited, Czech headers, DD.MM.YYYY dates, plain dot decimal numbers."""

    def setup_method(self):
        self.result = parse_file(
            (SAMPLE_DIR / "pohoda_ar_export.csv").read_bytes(),
            "pohoda_ar_export.csv",
        )

    def test_parses_successfully(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_detects_semicolon_delimiter(self):
        assert self.result.delimiter == ";"

    def test_detects_encoding(self):
        assert self.result.encoding is not None

    def test_finds_all_rows(self):
        assert self.result.total_rows == 15

    def test_finds_all_columns(self):
        assert len(self.result.headers) == 9
        assert "Číslo faktury" in self.result.headers
        assert "Zbývá uhradit" in self.result.headers

    def test_detects_date_columns(self):
        assert self.result.column_types["Datum vystavení"] == "date"
        assert self.result.column_types["Datum splatnosti"] == "date"

    def test_detects_numeric_columns(self):
        assert self.result.column_types["Celkem s DPH"] == "numeric"
        assert self.result.column_types["Zbývá uhradit"] == "numeric"

    def test_id_columns_stay_string(self):
        assert self.result.column_types["IČO"] == "string"

    def test_date_format_detected(self):
        assert self.result.date_format in ("DD.MM.YYYY", "D.M.YYYY")

    def test_numeric_values_converted(self):
        df = self.result.dataframe
        assert df.iloc[0]["Celkem s DPH"] == 45000.00

    def test_date_values_converted(self):
        df = self.result.dataframe
        assert df.iloc[0]["Datum splatnosti"] == datetime.date(2026, 1, 15)

    def test_paid_invoice_has_zero_balance(self):
        df = self.result.dataframe
        assert df.iloc[14]["Zbývá uhradit"] == 0.00

    def test_decimal_separator(self):
        assert self.result.decimal_separator == "."

    def test_thousands_separator(self):
        assert self.result.thousands_separator is None


class TestFakturoidCSV:
    """Comma-delimited, English headers, YYYY-MM-DD dates, plain dot decimal numbers, EUR."""

    def setup_method(self):
        self.result = parse_file(
            (SAMPLE_DIR / "fakturoid_ar_export.csv").read_bytes(),
            "fakturoid_ar_export.csv",
        )

    def test_parses_successfully(self):
        assert self.result.success is True

    def test_detects_comma_delimiter(self):
        assert self.result.delimiter == ","

    def test_finds_all_rows(self):
        assert self.result.total_rows == 15

    def test_detects_iso_dates(self):
        assert self.result.column_types["Issue Date"] == "date"
        assert self.result.date_format == "YYYY-MM-DD"

    def test_detects_numeric_columns(self):
        assert self.result.column_types["Total Amount"] == "numeric"
        assert self.result.column_types["Amount Due"] == "numeric"

    def test_status_column_stays_string(self):
        assert self.result.column_types["Status"] == "string"

    def test_date_values_converted(self):
        df = self.result.dataframe
        assert df.iloc[0]["Due Date"] == datetime.date(2026, 1, 18)

    def test_paid_invoice_has_zero_balance(self):
        df = self.result.dataframe
        assert df.iloc[14]["Amount Due"] == 0.00

    def test_decimal_separator(self):
        assert self.result.decimal_separator == "."


class TestMessyGenericCSV:
    """Comma-delimited, Czech headers, D.M.YYYY dates, space+comma numbers."""

    def setup_method(self):
        self.result = parse_file(
            (SAMPLE_DIR / "messy_generic_export.csv").read_bytes(),
            "messy_generic_export.csv",
        )

    def test_parses_successfully(self):
        assert self.result.success is True

    def test_detects_comma_delimiter(self):
        assert self.result.delimiter == ","

    def test_finds_all_rows(self):
        assert self.result.total_rows == 12

    def test_handles_space_comma_numbers(self):
        df = self.result.dataframe
        assert self.result.column_types["Castka"] == "numeric"
        assert df.iloc[0]["Castka"] == 45000.00

    def test_handles_partial_payment(self):
        df = self.result.dataframe
        assert df.iloc[3]["Zbyva"] == 78000.00

    def test_handles_single_digit_dates(self):
        df = self.result.dataframe
        assert df.iloc[0]["Vystaveno"] == datetime.date(2026, 1, 3)

    def test_handles_quoted_fields_with_commas(self):
        df = self.result.dataframe
        delta_row = df[df["Firma"].str.contains("Delta", na=False)].iloc[0]
        assert "Delta Stavby" in delta_row["Firma"]

    def test_handles_missing_company_name(self):
        df = self.result.dataframe
        row_11 = df.iloc[10]
        assert row_11["Firma"] == ""

    def test_preserves_all_columns(self):
        assert "Poznamka" in self.result.headers
        assert "Telefon" in self.result.headers

    def test_id_columns_stay_string(self):
        assert self.result.column_types["IC"] == "string"

    def test_decimal_separator(self):
        assert self.result.decimal_separator == ","

    def test_thousands_separator(self):
        assert self.result.thousands_separator == " "


class TestFrenchCSV:
    """Semicolon-delimited, French headers, DD/MM/YYYY dates, space+comma numbers, Windows-1252."""

    def setup_method(self):
        self.result = parse_file(
            (SAMPLE_DIR / "french_ar_export.csv").read_bytes(),
            "french_ar_export.csv",
        )

    def test_parses_successfully(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_detects_semicolon_delimiter(self):
        assert self.result.delimiter == ";"

    def test_detects_western_european_encoding(self):
        assert self.result.encoding is not None
        assert self.result.encoding.lower().replace("-", "").replace("_", "") in [
            "windows1252",
            "iso88591",
            "iso885915",
            "latin1",
            "cp1252",
        ]

    def test_finds_all_rows(self):
        assert self.result.total_rows == 12

    def test_finds_french_headers(self):
        headers_lower = [h.lower() for h in self.result.headers]
        assert any("facture" in h for h in headers_lower)
        assert any("payer" in h for h in headers_lower)

    def test_handles_slash_dates(self):
        assert self.result.date_format in ("DD/MM/YYYY", "D/M/YYYY")

    def test_date_values_converted_european_convention(self):
        df = self.result.dataframe
        date_col = [c for c in df.columns if "mission" in c.lower() or "émission" in c.lower()][0]
        assert df.iloc[0][date_col] == datetime.date(2026, 1, 3)

    def test_handles_space_comma_numbers(self):
        df = self.result.dataframe
        amount_col = [c for c in df.columns if "TTC" in c or "Montant" in c][0]
        assert self.result.column_types[amount_col] == "numeric"
        assert df.iloc[0][amount_col] == 12500.00

    def test_large_space_comma_number(self):
        df = self.result.dataframe
        amount_col = [c for c in df.columns if "TTC" in c or "Montant" in c][0]
        assert df.iloc[2][amount_col] == 45000.00

    def test_handles_accented_characters(self):
        df = self.result.dataframe
        name_col = [c for c in df.columns if "client" in c.lower() or "Nom" in c][0]
        all_names = " ".join(df[name_col].tolist())
        assert "â" in all_names or "Bâtiment" in all_names or "Batiment" in all_names

    def test_siret_stays_string(self):
        siret_col = [c for c in self.result.headers if "SIRET" in c.upper()][0]
        assert self.result.column_types[siret_col] == "string"

    def test_paid_invoice_has_zero(self):
        df = self.result.dataframe
        remaining_col = [c for c in df.columns if "Reste" in c or "payer" in c.lower()][0]
        assert df.iloc[11][remaining_col] == 0.00

    def test_decimal_separator(self):
        assert self.result.decimal_separator == ","

    def test_thousands_separator(self):
        assert self.result.thousands_separator == " "


class TestItalianCSV:
    """Semicolon-delimited, Italian headers, DD/MM/YYYY dates, dot+comma numbers."""

    def setup_method(self):
        self.result = parse_file(
            (SAMPLE_DIR / "italian_ar_export.csv").read_bytes(),
            "italian_ar_export.csv",
        )

    def test_parses_successfully(self):
        assert self.result.success is True
        assert self.result.error is None

    def test_detects_semicolon_delimiter(self):
        assert self.result.delimiter == ";"

    def test_finds_all_rows(self):
        assert self.result.total_rows == 12

    def test_finds_italian_headers(self):
        assert "Numero fattura" in self.result.headers
        assert "Importo residuo" in self.result.headers

    def test_handles_dot_comma_numbers(self):
        df = self.result.dataframe
        assert self.result.column_types["Importo lordo"] == "numeric"
        assert df.iloc[0]["Importo lordo"] == 12500.00

    def test_large_dot_comma_number(self):
        df = self.result.dataframe
        assert df.iloc[2]["Importo lordo"] == 45000.00

    def test_partita_iva_stays_string(self):
        assert self.result.column_types["Partita IVA"] == "string"

    def test_handles_slash_dates(self):
        assert self.result.date_format in ("DD/MM/YYYY", "D/M/YYYY")

    def test_date_values_converted(self):
        df = self.result.dataframe
        assert df.iloc[0]["Data scadenza"] == datetime.date(2026, 1, 18)

    def test_partial_payment(self):
        df = self.result.dataframe
        assert df.iloc[4]["Importo residuo"] == 1050.00

    def test_paid_invoice_has_zero(self):
        df = self.result.dataframe
        assert df.iloc[11]["Importo residuo"] == 0.00

    def test_decimal_separator(self):
        assert self.result.decimal_separator == ","

    def test_thousands_separator(self):
        assert self.result.thousands_separator == "."


class TestPlainDotDecimal:
    """Inline test for plain dot-decimal pattern (e.g., 45000.00) with no thousands separator.
    Verifies that values without thousands groups parse correctly."""

    def setup_method(self):
        content = (
            b"Invoice,Client,Amount,Balance\n"
            b"INV-001,Smith Corp,45000.00,45000.00\n"
            b"INV-002,Jones Ltd,1200.50,1200.50\n"
            b"INV-003,Brown Inc,125000.75,62500.38\n"
        )
        self.result = parse_file(content, "comma_dot_test.csv")

    def test_parses_successfully(self):
        assert self.result.success is True

    def test_detects_plain_dot_decimal(self):
        assert self.result.column_types["Amount"] == "numeric"
        assert self.result.decimal_separator == "."

    def test_values_correct(self):
        df = self.result.dataframe
        assert df.iloc[0]["Amount"] == 45000.00
        assert df.iloc[2]["Balance"] == 62500.38


class TestCommaThousandsExplicit:
    """Explicit test for comma-as-thousands + dot-decimal (e.g., 45,000.00)."""

    def setup_method(self):
        content = (
            b"Invoice,Client,Total,Remaining\n"
            b'INV-001,Acme,"45,000.00","45,000.00"\n'
            b'INV-002,Beta,"1,200.50","600.25"\n'
            b'INV-003,Gamma,"125,000.75","125,000.75"\n'
        )
        self.result = parse_file(content, "comma_thousands_test.csv")

    def test_parses_successfully(self):
        assert self.result.success is True

    def test_detects_comma_thousands(self):
        assert self.result.column_types["Total"] == "numeric"
        assert self.result.decimal_separator == "."
        assert self.result.thousands_separator == ","

    def test_values_correct(self):
        df = self.result.dataframe
        assert df.iloc[0]["Total"] == 45000.00
        assert df.iloc[1]["Remaining"] == 600.25
        assert df.iloc[2]["Total"] == 125000.75


class TestEdgeCases:
    """Error handling and edge cases."""

    def test_unsupported_file_type_pdf(self):
        result = parse_file(b"some content", "document.pdf")
        assert result.success is False
        assert "Unsupported" in result.error

    def test_unsupported_file_type_xls(self):
        result = parse_file(b"some content", "legacy.xls")
        assert result.success is False
        assert "xls" in result.error.lower()

    def test_empty_file(self):
        result = parse_file(b"", "empty.csv")
        assert result.success is False

    def test_header_only_file(self):
        content = b"Name,Amount,Date\n"
        result = parse_file(content, "header_only.csv")
        assert result.success is True
        assert result.total_rows == 0

    def test_tsv_file(self):
        content = b"Name\tAmount\tDate\nACME\t1000.00\t2026-01-15\n"
        result = parse_file(content, "data.tsv")
        assert result.success is True
        assert result.delimiter == "\t"
        assert result.total_rows == 1

    def test_pure_integer_column_is_string(self):
        content = b"ID,Name,RegNumber\n1,Foo,12345678\n2,Bar,87654321\n3,Baz,11223344\n"
        result = parse_file(content, "ids.csv")
        assert result.success is True
        assert result.column_types["RegNumber"] == "string"
        assert result.column_types["ID"] == "string"
