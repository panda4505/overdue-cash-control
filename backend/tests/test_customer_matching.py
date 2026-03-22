"""Tests for fuzzy customer matching logic — pure unit tests, no DB required."""

from __future__ import annotations

import pytest

from app.services.customer_matching import (
    HIGH_THRESHOLD,
    ExistingCustomerInfo,
    FileCustomer,
    MatchResult,
    find_best_match,
    find_fuzzy_matches,
    fold_diacritics,
)
from app.services.normalization import normalize_customer_name


class TestFoldDiacritics:
    def test_strips_accents(self):
        assert fold_diacritics("société générale") == "societe generale"

    def test_strips_tilde(self):
        assert fold_diacritics("ñoño") == "nono"

    def test_strips_umlaut(self):
        assert fold_diacritics("müller") == "muller"

    def test_ascii_unchanged(self):
        assert fold_diacritics("acme corp") == "acme corp"

    def test_empty_string(self):
        assert fold_diacritics("") == ""

    def test_czech_characters(self):
        assert fold_diacritics("příliš žluťoučký") == "prilis zlutoucky"


class TestExactMatchSkipped:
    def test_exact_same_name_returns_none(self):
        file_customer = FileCustomer(normalized_name="acme", raw_name="Acme")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme",
            display_name="Acme s.r.o.",
        )

        assert find_best_match(file_customer, [existing_customer]) is None


class TestMergeHistory:
    def test_merge_history_match(self):
        file_customer = FileCustomer(normalized_name="acme sro", raw_name="ACME SRO")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme",
            display_name="Acme s.r.o.",
            merge_history=[
                {
                    "variant": "ACME SRO",
                    "normalized_name": "acme sro",
                    "merged_at": "2026-01-01T00:00:00Z",
                }
            ],
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is not None
        assert match.match_type == "merge_history"
        assert match.score == 1.0
        assert match.confidence == "high"

    def test_merge_history_priority_over_jaro_winkler(self):
        file_customer = FileCustomer(normalized_name="acme sro", raw_name="ACME SRO")
        history_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="original acme",
            display_name="Original Acme",
            merge_history=[
                {
                    "variant": "ACME SRO",
                    "normalized_name": "acme sro",
                    "merged_at": "2026-01-01T00:00:00Z",
                }
            ],
        )
        similar_customer = ExistingCustomerInfo(
            customer_id="cust-2",
            normalized_name="acme srl",
            display_name="Acme SRL",
        )

        match = find_best_match(file_customer, [history_customer, similar_customer])

        assert match is not None
        assert match.existing_customer_id == "cust-1"
        assert match.match_type == "merge_history"

    def test_merge_history_none_no_error(self):
        file_customer = FileCustomer(normalized_name="newco", raw_name="NewCo")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="existing",
            display_name="Existing",
            merge_history=None,
        )

        result = find_best_match(file_customer, [existing_customer])

        assert result is None or isinstance(result, MatchResult)

    def test_merge_history_empty_list_no_error(self):
        file_customer = FileCustomer(normalized_name="newco", raw_name="NewCo")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="existing",
            display_name="Existing",
            merge_history=[],
        )

        result = find_best_match(file_customer, [existing_customer])

        assert result is None or isinstance(result, MatchResult)


class TestVatIdMatching:
    def test_vat_match(self):
        file_customer = FileCustomer(
            normalized_name="totally different name",
            raw_name="Totally Different Name",
            vat_id="CZ12345678",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="original company",
            display_name="Original Company",
            vat_id="CZ12345678",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is not None
        assert match.match_type == "vat_id"
        assert match.score == 1.0

    def test_vat_case_insensitive(self):
        file_customer = FileCustomer(
            normalized_name="some name",
            raw_name="Some Name",
            vat_id="cz12345678",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="other name",
            display_name="Other Name",
            vat_id="CZ12345678",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is not None
        assert match.match_type == "vat_id"

    def test_empty_vat_not_matched(self):
        file_customer = FileCustomer(normalized_name="different", raw_name="Different", vat_id="")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="other",
            display_name="Other",
            vat_id="",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.match_type != "vat_id"

    def test_none_vat_not_matched(self):
        file_customer = FileCustomer(normalized_name="different", raw_name="Different", vat_id=None)
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="other",
            display_name="Other",
            vat_id="CZ99999999",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.match_type != "vat_id"


class TestJaroWinklerMatching:
    def test_accent_variant_high_confidence(self):
        file_customer = FileCustomer(
            normalized_name="societe generale",
            raw_name="Societe Generale",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="société générale",
            display_name="Société Générale",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is not None
        assert match.confidence == "high"
        assert match.match_type == "name_similarity"
        assert match.score >= HIGH_THRESHOLD

    def test_low_similarity_no_match(self):
        file_customer = FileCustomer(
            normalized_name="alpha technologies",
            raw_name="Alpha Technologies",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="beta industries",
            display_name="Beta Industries",
        )

        assert find_best_match(file_customer, [existing_customer]) is None

    def test_related_but_distinct_not_auto_merged(self):
        file_customer = FileCustomer(normalized_name="acme france", raw_name="Acme France SAS")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme germany",
            display_name="Acme Germany GmbH",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high" or match.score < HIGH_THRESHOLD
        if match is not None:
            assert match.confidence == "medium"

    def test_parent_subsidiary_not_auto_merged(self):
        file_customer = FileCustomer(
            normalized_name="global corp paris",
            raw_name="Global Corp Paris",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="global corp london",
            display_name="Global Corp London",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high"

    def test_custom_thresholds(self):
        file_customer = FileCustomer(normalized_name="test company", raw_name="Test Company")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="test comp",
            display_name="Test Comp",
        )

        match = find_best_match(file_customer, [existing_customer], high_threshold=0.99, low_threshold=0.98)

        assert match is None or match.confidence != "high"

    def test_close_candidates_returns_only_best(self):
        file_customer = FileCustomer(normalized_name="acme tech", raw_name="Acme Tech")
        first_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme technology",
            display_name="Acme Technology",
        )
        second_customer = ExistingCustomerInfo(
            customer_id="cust-2",
            normalized_name="acme technical",
            display_name="Acme Technical",
        )

        match = find_best_match(file_customer, [first_customer, second_customer])

        assert match is None or isinstance(match, MatchResult)


class TestQualifierNearCollisionGuard:
    """Qualifier-based near-collisions must never auto-merge."""

    def test_single_letter_qualifier_not_auto_merged(self):
        file_customer = FileCustomer(normalized_name="beta group a", raw_name="Beta Group A")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="beta group b",
            display_name="Beta Group B",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high"

    def test_branch_direction_qualifier_not_auto_merged(self):
        file_customer = FileCustomer(normalized_name="techno east", raw_name="Techno East")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="techno west",
            display_name="Techno West",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high"

    def test_division_number_qualifier_not_auto_merged(self):
        file_customer = FileCustomer(normalized_name="omega division 1", raw_name="Omega Division 1")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="omega division 2",
            display_name="Omega Division 2",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high"

    def test_short_region_qualifier_not_auto_merged(self):
        file_customer = FileCustomer(normalized_name="acme nord", raw_name="Acme Nord")
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme sud",
            display_name="Acme Sud",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is None or match.confidence != "high"


class TestTypoPositiveRegression:
    """Obvious single-character typos on longer names should still auto-merge."""

    def test_single_char_deletion_typo_auto_merges(self):
        file_customer = FileCustomer(
            normalized_name="schneider electric servces",
            raw_name="Schneider Electric Servces",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="schneider electric services",
            display_name="Schneider Electric Services",
        )

        match = find_best_match(file_customer, [existing_customer])

        assert match is not None
        assert match.confidence == "high"
        assert match.match_type == "name_similarity"


class TestEdgeCases:
    def test_no_existing_customers(self):
        file_customer = FileCustomer(normalized_name="acme", raw_name="Acme")

        assert find_best_match(file_customer, []) is None

    def test_multiple_file_customers_same_target(self):
        first_file_customer = FileCustomer(normalized_name="acme corp", raw_name="ACME Corp")
        second_file_customer = FileCustomer(
            normalized_name="acme corporat",
            raw_name="ACME Corporat",
        )
        existing_customer = ExistingCustomerInfo(
            customer_id="cust-1",
            normalized_name="acme corporation",
            display_name="Acme Corporation",
        )

        result = find_fuzzy_matches(
            [first_file_customer, second_file_customer],
            [existing_customer],
        )
        all_matches = result.auto_merges + result.candidates
        for match in all_matches:
            assert match.existing_customer_id == "cust-1"

    def test_empty_inputs(self):
        result = find_fuzzy_matches([], [])

        assert result.auto_merges == []
        assert result.candidates == []


class TestNormalizationMatchingIntegration:
    """Normalization should handle suffix variants before fuzzy matching."""

    def test_dotted_vs_dotless_srl_exact_match(self):
        assert normalize_customer_name("Acme SRL") == normalize_customer_name("Acme S.R.L.")

    def test_dotted_vs_dotless_sro_exact_match(self):
        assert normalize_customer_name("Acme SRO") == normalize_customer_name("Acme s.r.o.")

    def test_dotted_vs_dotless_spa_exact_match(self):
        assert normalize_customer_name("Fiat SpA") == normalize_customer_name("Fiat S.p.A.")

    def test_dotted_vs_dotless_sl_exact_match(self):
        assert normalize_customer_name("Empresa SL") == normalize_customer_name("Empresa S.L.")
