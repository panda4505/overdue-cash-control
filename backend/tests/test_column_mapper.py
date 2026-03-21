import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.file_parser import ParseResult, parse_file
from app.services.column_mapper import (
    AUXILIARY_FIELDS,
    CANONICAL_FIELDS,
    CORE_FIELDS,
    MappingResult,
    map_columns,
)

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample-data"


def _parse(filename: str):
    """Helper to parse a sample file."""

    return parse_file((SAMPLE_DIR / filename).read_bytes(), filename)


class TestPohodaMapping:
    """Czech headers from Pohoda export. Must map fully via dictionary — no LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("pohoda_ar_export.csv")
        self.llm_patcher = patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock)
        self.mock_llm = self.llm_patcher.start()

    def teardown_method(self):
        self.llm_patcher.stop()

    @pytest.mark.asyncio
    async def test_maps_successfully(self):
        result = await map_columns(self.parse_result)
        assert result.success is True
        assert result.method == "deterministic"

    @pytest.mark.asyncio
    async def test_llm_never_called(self):
        await map_columns(self.parse_result)
        assert self.mock_llm.await_count == 0

    @pytest.mark.asyncio
    async def test_maps_required_fields(self):
        result = await map_columns(self.parse_result)
        mapped_fields = {m.target_field for m in result.mappings}
        assert "invoice_number" in mapped_fields
        assert "customer_name" in mapped_fields
        assert "due_date" in mapped_fields
        assert "outstanding_amount" in mapped_fields or "gross_amount" in mapped_fields

    @pytest.mark.asyncio
    async def test_no_unmapped_required_fields(self):
        result = await map_columns(self.parse_result)
        assert len(result.unmapped_required_fields) == 0

    @pytest.mark.asyncio
    async def test_maps_correct_columns(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Číslo faktury"
        assert field_to_source["customer_name"] == "Odběratel"
        assert field_to_source["due_date"] == "Datum splatnosti"
        assert field_to_source.get("outstanding_amount") == "Zbývá uhradit"
        assert field_to_source.get("gross_amount") == "Celkem s DPH"

    @pytest.mark.asyncio
    async def test_maps_optional_fields(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source.get("company_id") == "IČO"
        assert field_to_source.get("email") == "Email"
        assert field_to_source.get("issue_date") == "Datum vystavení"
        assert field_to_source.get("currency") == "Měna"

    @pytest.mark.asyncio
    async def test_confidence_is_high(self):
        result = await map_columns(self.parse_result)
        assert result.overall_confidence >= 0.8

    @pytest.mark.asyncio
    async def test_amount_fallback_not_active(self):
        result = await map_columns(self.parse_result)
        assert result.amount_fallback_active is False

    @pytest.mark.asyncio
    async def test_tiers_are_correct(self):
        result = await map_columns(self.parse_result)
        for mapping in result.mappings:
            if mapping.target_field in CORE_FIELDS:
                assert mapping.tier == "core"
            elif mapping.target_field in AUXILIARY_FIELDS:
                assert mapping.tier == "auxiliary"


class TestFakturoidMapping:
    """English headers from Fakturoid export. Must map fully via dictionary — no LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("fakturoid_ar_export.csv")
        self.llm_patcher = patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock)
        self.mock_llm = self.llm_patcher.start()

    def teardown_method(self):
        self.llm_patcher.stop()

    @pytest.mark.asyncio
    async def test_maps_successfully(self):
        result = await map_columns(self.parse_result)
        assert result.success is True
        assert result.method == "deterministic"

    @pytest.mark.asyncio
    async def test_llm_never_called(self):
        await map_columns(self.parse_result)
        assert self.mock_llm.await_count == 0

    @pytest.mark.asyncio
    async def test_maps_correct_columns(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Invoice Number"
        assert field_to_source["customer_name"] == "Client Name"
        assert field_to_source["due_date"] == "Due Date"
        assert field_to_source.get("outstanding_amount") == "Amount Due"
        assert field_to_source.get("gross_amount") == "Total Amount"
        assert field_to_source.get("email") == "Client Email"
        assert field_to_source.get("status") == "Status"

    @pytest.mark.asyncio
    async def test_status_is_auxiliary(self):
        result = await map_columns(self.parse_result)
        status_mapping = next((m for m in result.mappings if m.target_field == "status"), None)
        assert status_mapping is not None
        assert status_mapping.tier == "auxiliary"

    @pytest.mark.asyncio
    async def test_no_unmapped_required(self):
        result = await map_columns(self.parse_result)
        assert len(result.unmapped_required_fields) == 0


class TestMessyGenericMapping:
    """Czech headers from messy export — abbreviated/informal headers. Must map via dictionary — no LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("messy_generic_export.csv")
        self.llm_patcher = patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock)
        self.mock_llm = self.llm_patcher.start()

    def teardown_method(self):
        self.llm_patcher.stop()

    @pytest.mark.asyncio
    async def test_maps_successfully(self):
        result = await map_columns(self.parse_result)
        assert result.success is True

    @pytest.mark.asyncio
    async def test_llm_never_called(self):
        await map_columns(self.parse_result)
        assert self.mock_llm.await_count == 0

    @pytest.mark.asyncio
    async def test_maps_required_fields(self):
        result = await map_columns(self.parse_result)
        mapped_fields = {m.target_field for m in result.mappings}
        assert "invoice_number" in mapped_fields
        assert "customer_name" in mapped_fields
        assert "due_date" in mapped_fields
        assert "outstanding_amount" in mapped_fields or "gross_amount" in mapped_fields

    @pytest.mark.asyncio
    async def test_maps_correct_columns(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Faktura"
        assert field_to_source["customer_name"] == "Firma"
        assert field_to_source["due_date"] == "Splatnost"
        assert field_to_source.get("company_id") == "IC"
        assert field_to_source.get("vat_id") == "DIC"
        assert field_to_source.get("phone") == "Telefon"
        assert field_to_source.get("notes") == "Poznamka"
        assert field_to_source.get("contact_name") == "Kontakt"


class TestFrenchMapping:
    """French headers from Sage/Cegid-style export. Must map fully via dictionary — no LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("french_ar_export.csv")
        self.llm_patcher = patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock)
        self.mock_llm = self.llm_patcher.start()

    def teardown_method(self):
        self.llm_patcher.stop()

    @pytest.mark.asyncio
    async def test_maps_successfully(self):
        result = await map_columns(self.parse_result)
        assert result.success is True
        assert result.method == "deterministic"

    @pytest.mark.asyncio
    async def test_llm_never_called(self):
        await map_columns(self.parse_result)
        assert self.mock_llm.await_count == 0

    @pytest.mark.asyncio
    async def test_maps_correct_columns(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Numéro de facture"
        assert field_to_source["customer_name"] == "Nom du client"
        assert field_to_source["due_date"] == "Date d'échéance"
        assert field_to_source.get("outstanding_amount") == "Reste à payer"
        assert field_to_source.get("gross_amount") == "Montant TTC"
        assert field_to_source.get("company_id") == "SIRET"
        assert field_to_source.get("email") == "Email client"
        assert field_to_source.get("issue_date") == "Date d'émission"
        assert field_to_source.get("currency") == "Devise"
        assert field_to_source.get("status") == "Statut"

    @pytest.mark.asyncio
    async def test_no_unmapped_required(self):
        result = await map_columns(self.parse_result)
        assert len(result.unmapped_required_fields) == 0

    @pytest.mark.asyncio
    async def test_high_confidence(self):
        result = await map_columns(self.parse_result)
        assert result.overall_confidence >= 0.8


class TestItalianMapping:
    """Italian headers from Fatture in Cloud-style export. Must map fully via dictionary — no LLM."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("italian_ar_export.csv")
        self.llm_patcher = patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock)
        self.mock_llm = self.llm_patcher.start()

    def teardown_method(self):
        self.llm_patcher.stop()

    @pytest.mark.asyncio
    async def test_maps_successfully(self):
        result = await map_columns(self.parse_result)
        assert result.success is True
        assert result.method == "deterministic"

    @pytest.mark.asyncio
    async def test_llm_never_called(self):
        await map_columns(self.parse_result)
        assert self.mock_llm.await_count == 0

    @pytest.mark.asyncio
    async def test_maps_correct_columns(self):
        result = await map_columns(self.parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Numero fattura"
        assert field_to_source["customer_name"] == "Ragione sociale"
        assert field_to_source["due_date"] == "Data scadenza"
        assert field_to_source.get("outstanding_amount") == "Importo residuo"
        assert field_to_source.get("gross_amount") == "Importo lordo"
        assert field_to_source.get("vat_id") == "Partita IVA"
        assert field_to_source.get("email") == "Email"
        assert field_to_source.get("issue_date") == "Data emissione"
        assert field_to_source.get("currency") == "Valuta"
        assert field_to_source.get("status") == "Stato"

    @pytest.mark.asyncio
    async def test_no_unmapped_required(self):
        result = await map_columns(self.parse_result)
        assert len(result.unmapped_required_fields) == 0


class TestTemplateApplication:
    """Test applying a saved template mapping."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.parse_result = _parse("pohoda_ar_export.csv")

    @pytest.mark.asyncio
    async def test_template_applied_successfully(self):
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Odběratel",
            "due_date": "Datum splatnosti",
            "gross_amount": "Celkem s DPH",
            "outstanding_amount": "Zbývá uhradit",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        assert result.method == "mixed"
        template_mappings = [m for m in result.mappings if m.method == "template"]
        assert all(m.confidence == 1.0 for m in template_mappings)

    @pytest.mark.asyncio
    async def test_template_enrichment_adds_optional_fields(self):
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Odběratel",
            "due_date": "Datum splatnosti",
            "outstanding_amount": "Zbývá uhradit",
            "gross_amount": "Celkem s DPH",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source.get("email") == "Email"
        assert field_to_source.get("company_id") == "IČO"
        assert field_to_source.get("currency") == "Měna"
        assert field_to_source.get("issue_date") == "Datum vystavení"
        assert result.method == "mixed"

    @pytest.mark.asyncio
    async def test_template_with_missing_column_warns(self):
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Odběratel",
            "due_date": "Datum splatnosti",
            "outstanding_amount": "Zbývá uhradit",
            "gross_amount": "NONEXISTENT COLUMN",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        assert any("NONEXISTENT" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_template_all_missing_falls_back(self):
        template = {
            "invoice_number": "WRONG1",
            "customer_name": "WRONG2",
            "due_date": "WRONG3",
            "outstanding_amount": "WRONG4",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        assert result.method != "template"

    @pytest.mark.asyncio
    async def test_template_duplicate_source_rejected(self):
        template = {
            "invoice_number": "Číslo faktury",
            "customer_name": "Číslo faktury",
            "due_date": "Datum splatnosti",
            "outstanding_amount": "Zbývá uhradit",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        assert result.method == "deterministic"
        assert any(
            "same source column" in warning.lower() or "duplicate" in warning.lower()
            for warning in result.warnings
        )

    @pytest.mark.asyncio
    async def test_template_matches_despite_accent_case_differences(self):
        template = {
            "invoice_number": "CISLO FAKTURY",
            "customer_name": "odberatel",
            "due_date": "Datum Splatnosti",
        }
        result = await map_columns(self.parse_result, existing_mapping=template)
        assert result.success is True
        assert result.method in {"template", "mixed"}
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source["invoice_number"] == "Číslo faktury"
        assert field_to_source["customer_name"] == "Odběratel"
        assert field_to_source["due_date"] == "Datum splatnosti"


class TestLLMFallback:
    """Test LLM fallback with mocked llm_complete()."""

    @pytest.mark.asyncio
    async def test_llm_called_for_unknown_headers(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "Col_A": ["INV-001", "INV-002"],
                "Col_B": ["ACME", "Beta"],
                "Col_C": ["2026-01-15", "2026-02-01"],
                "Col_D": ["1000.00", "2000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="unknown.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=2,
            column_types={
                "Col_A": "string",
                "Col_B": "string",
                "Col_C": "date",
                "Col_D": "numeric",
            },
        )

        mock_response = '{"Col_A": {"field": "invoice_number", "confidence": 0.9}, "Col_B": {"field": "customer_name", "confidence": 0.85}, "Col_C": {"field": "due_date", "confidence": 0.9}, "Col_D": {"field": "outstanding_amount", "confidence": 0.8}}'

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await map_columns(parse_result)
            assert result.success is True
            assert "llm" in result.method
            mapped_fields = {m.target_field for m in result.mappings}
            assert "invoice_number" in mapped_fields
            assert "customer_name" in mapped_fields

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_gracefully(self):
        import pandas as pd

        df = pd.DataFrame({"Invoice Number": ["INV-001"], "Col_Y": ["ACME"]})
        parse_result = ParseResult(
            success=True,
            filename="unknown.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={"Invoice Number": "string", "Col_Y": "string"},
        )

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            side_effect=RuntimeError("All LLM providers failed"),
        ):
            result = await map_columns(parse_result)
            assert result.success is True
            assert any("LLM fallback failed" in warning for warning in result.warnings)

    @pytest.mark.asyncio
    async def test_llm_bad_json_handled(self):
        import pandas as pd

        df = pd.DataFrame({"Invoice Number": ["INV-001"], "Col_A": ["test"]})
        parse_result = ParseResult(
            success=True,
            filename="unknown.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={"Invoice Number": "string", "Col_A": "string"},
        )

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            return_value="This is not JSON",
        ):
            result = await map_columns(parse_result)
            assert result.success is True
            assert any(
                "JSON" in warning or "json" in warning.lower() or "parse" in warning.lower()
                for warning in result.warnings
            )

    @pytest.mark.asyncio
    async def test_llm_cannot_override_strong_deterministic(self):
        """LLM should not override a deterministic match with confidence >= 0.7."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Col_Unknown": ["ACME"],
                "Due Date": ["2026-01-15"],
                "Amount Due": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="partial.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Col_Unknown": "string",
                "Due Date": "date",
                "Amount Due": "numeric",
            },
        )

        mock_response = '{"Invoice Number": {"field": "notes", "confidence": 0.95}, "Col_Unknown": {"field": "customer_name", "confidence": 0.85}, "Due Date": {"field": "due_date", "confidence": 0.9}, "Amount Due": {"field": "outstanding_amount", "confidence": 0.9}}'

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await map_columns(parse_result)
            field_to_source = {m.target_field: m.source_column for m in result.mappings}
            assert field_to_source.get("invoice_number") == "Invoice Number"

    @pytest.mark.asyncio
    async def test_llm_hallucinated_source_column_ignored(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "Col_A": ["INV-001"],
                "Col_B": ["ACME"],
                "Col_C": ["2026-01-15"],
                "Col_D": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="unknown.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Col_A": "string",
                "Col_B": "string",
                "Col_C": "date",
                "Col_D": "numeric",
            },
        )

        mock_response = (
            '{"Phantom_Column": {"field": "notes", "confidence": 0.9}, '
            '"Col_A": {"field": "invoice_number", "confidence": 0.9}, '
            '"Col_B": {"field": "customer_name", "confidence": 0.85}, '
            '"Col_C": {"field": "due_date", "confidence": 0.9}, '
            '"Col_D": {"field": "outstanding_amount", "confidence": 0.8}}'
        )

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await map_columns(parse_result)
            assert result.success is True
            assert all(mapping.source_column != "Phantom_Column" for mapping in result.mappings)
            assert any("Phantom_Column" in warning for warning in result.warnings)
            field_to_source = {m.target_field: m.source_column for m in result.mappings}
            assert field_to_source.get("invoice_number") == "Col_A"
            assert field_to_source.get("customer_name") == "Col_B"

    @pytest.mark.asyncio
    async def test_llm_hallucinated_target_field_ignored(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "Col_A": ["INV-001"],
                "Col_B": ["ACME"],
                "Col_C": ["2026-01-15"],
                "Col_D": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="unknown.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Col_A": "string",
                "Col_B": "string",
                "Col_C": "date",
                "Col_D": "numeric",
            },
        )

        mock_response = (
            '{"Col_A": {"field": "magic_field", "confidence": 0.9}, '
            '"Col_B": {"field": "customer_name", "confidence": 0.85}, '
            '"Col_C": {"field": "due_date", "confidence": 0.9}, '
            '"Col_D": {"field": "outstanding_amount", "confidence": 0.8}}'
        )

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await map_columns(parse_result)
            assert all(mapping.target_field != "magic_field" for mapping in result.mappings)
            assert any("magic_field" in warning for warning in result.warnings)
            field_to_source = {m.target_field: m.source_column for m in result.mappings}
            assert field_to_source.get("customer_name") == "Col_B"


class TestConflictsAndEdgeCases:
    """Conflict resolution, amount fallback, and edge cases."""

    @pytest.mark.asyncio
    async def test_empty_parse_result(self):
        result = await map_columns(ParseResult(success=False, filename="bad.csv", error="parse failed"))
        assert result.success is False

    @pytest.mark.asyncio
    async def test_duplicate_target_resolved(self):
        """Two columns mapping to same target: higher confidence wins."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Invoice No": ["INV-001"],
                "Customer": ["ACME"],
                "Due Date": ["2026-01-15"],
                "Amount Due": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="dupes.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Invoice No": "string",
                "Customer": "string",
                "Due Date": "date",
                "Amount Due": "numeric",
            },
        )
        result = await map_columns(parse_result)
        invoice_mappings = [m for m in result.mappings if m.target_field == "invoice_number"]
        assert len(invoice_mappings) == 1
        assert len(result.conflicts) >= 1
        conflict = next(c for c in result.conflicts if c.target_field == "invoice_number")
        assert conflict.winner in ("Invoice Number", "Invoice No")
        assert conflict.loser in ("Invoice Number", "Invoice No")
        assert conflict.winner != conflict.loser

    @pytest.mark.asyncio
    async def test_amount_fallback_when_only_gross(self):
        """If only gross_amount is mapped, amount_fallback_active should be True."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Customer": ["ACME"],
                "Due Date": ["2026-01-15"],
                "Total Amount": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="gross_only.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Customer": "string",
                "Due Date": "date",
                "Total Amount": "numeric",
            },
        )

        with patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock, return_value="{}"):
            result = await map_columns(parse_result)
            assert result.amount_fallback_active is True
            assert "outstanding_amount" not in result.unmapped_required_fields

    @pytest.mark.asyncio
    async def test_no_amount_at_all_flagged(self):
        """If neither amount field is mapped, it's flagged as unmapped."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Customer": ["ACME"],
                "Due Date": ["2026-01-15"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="no_amount.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Customer": "string",
                "Due Date": "date",
            },
        )

        with patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock, return_value="{}"):
            result = await map_columns(parse_result)
            assert "outstanding_amount" in result.unmapped_required_fields

    @pytest.mark.asyncio
    async def test_status_not_confused_with_amount(self):
        """Status column should map to status, not to an amount field."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Client Name": ["ACME"],
                "Due Date": ["2026-01-15"],
                "Amount Due": ["1000.00"],
                "Status": ["overdue"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="with_status.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Client Name": "string",
                "Due Date": "date",
                "Amount Due": "numeric",
                "Status": "string",
            },
        )
        result = await map_columns(parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source.get("status") == "Status"
        assert field_to_source.get("outstanding_amount") == "Amount Due"
        assert "Status" not in [
            mapping.source_column
            for mapping in result.mappings
            if mapping.target_field in ("outstanding_amount", "gross_amount")
        ]

    @pytest.mark.asyncio
    async def test_total_and_amount_due_not_collapsed(self):
        """Total Amount and Amount Due should map to different target fields."""

        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Client Name": ["ACME"],
                "Due Date": ["2026-01-15"],
                "Total Amount": ["1500.00"],
                "Amount Due": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="two_amounts.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Client Name": "string",
                "Due Date": "date",
                "Total Amount": "numeric",
                "Amount Due": "numeric",
            },
        )
        result = await map_columns(parse_result)
        field_to_source = {m.target_field: m.source_column for m in result.mappings}
        assert field_to_source.get("gross_amount") == "Total Amount"
        assert field_to_source.get("outstanding_amount") == "Amount Due"

    @pytest.mark.asyncio
    async def test_partial_matching_blocked_for_short_headers(self):
        import pandas as pd

        df = pd.DataFrame({"Facture": ["FA-001"], "Nom": ["ACME"]})
        parse_result = ParseResult(
            success=True,
            filename="short_headers.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={"Facture": "string", "Nom": "string"},
        )

        with patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock, return_value="{}"):
            result = await map_columns(parse_result)
            mapped_sources = {mapping.source_column for mapping in result.mappings}
            assert "Facture" not in mapped_sources
            assert "Nom" not in mapped_sources
            assert "Facture" in result.unmapped_source_columns
            assert "Nom" in result.unmapped_source_columns

    @pytest.mark.asyncio
    async def test_type_compatible_candidate_preferred(self):
        import pandas as pd

        df = pd.DataFrame(
            {
                "Invoice Number": ["INV-001"],
                "Customer": ["ACME"],
                "Date Due": ["2026-01-15"],
                "Payment Due": ["soon"],
                "Amount Due": ["1000.00"],
            }
        )
        parse_result = ParseResult(
            success=True,
            filename="type_preference.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={
                "Invoice Number": "string",
                "Customer": "string",
                "Date Due": "date",
                "Payment Due": "string",
                "Amount Due": "numeric",
            },
        )

        with patch("app.services.column_mapper.llm_complete", new_callable=AsyncMock, return_value="{}"):
            result = await map_columns(parse_result)
            field_to_source = {m.target_field: m.source_column for m in result.mappings}
            assert field_to_source.get("due_date") == "Date Due"
            conflict = next(c for c in result.conflicts if c.target_field == "due_date")
            assert conflict.loser == "Payment Due"

    @pytest.mark.asyncio
    async def test_llm_failure_zero_deterministic_returns_failure(self):
        import pandas as pd

        df = pd.DataFrame({"Xxx": ["a"], "Yyy": ["b"], "Zzz": ["c"]})
        parse_result = ParseResult(
            success=True,
            filename="zero_matches.csv",
            headers=list(df.columns),
            dataframe=df,
            total_rows=1,
            column_types={"Xxx": "string", "Yyy": "string", "Zzz": "string"},
        )

        with patch(
            "app.services.column_mapper.llm_complete",
            new_callable=AsyncMock,
            side_effect=RuntimeError("All LLM providers failed"),
        ):
            result = await map_columns(parse_result)
            assert result.success is False
            assert result.mappings == []
            assert any("LLM fallback failed" in warning for warning in result.warnings)
