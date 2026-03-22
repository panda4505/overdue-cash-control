"""Unit tests for anomaly_detection — pure logic, no database."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.anomaly_detection import (
    CLUSTER_RISK_THRESHOLD,
    OVERDUE_SPIKE_DELTA,
    OVERDUE_SPIKE_FLOOR,
    Anomaly,
    anomaly_to_dict,
    detect_customer_anomalies,
    detect_invoice_anomalies,
)


class TestDetectInvoiceAnomalies:
    def test_balance_increase_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=1500.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "balance_increase"
        assert anomalies[0].details["previous_amount"] == 1000.0
        assert anomalies[0].details["new_amount"] == 1500.0
        assert anomalies[0].details["increase"] == 500.0
        assert anomalies[0].invoice_id == "inv-1"
        assert anomalies[0].customer_id == "cust-1"

    def test_balance_decrease_not_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=500.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 0

    def test_balance_unchanged_not_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=1000.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 0

    def test_due_date_change_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=1000.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 2, 28),
        )
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "due_date_change"
        assert anomalies[0].details["previous_due_date"] == "2026-01-15"
        assert anomalies[0].details["new_due_date"] == "2026-02-28"

    def test_due_date_unchanged_not_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=1000.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 0

    def test_due_date_change_not_flagged_when_existing_is_none(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=1000.0,
            new_outstanding=1000.0,
            existing_due_date=None,
            new_due_date=date(2026, 2, 28),
        )
        assert all(a.anomaly_type != "due_date_change" for a in anomalies)

    def test_reappearance_flagged(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="possibly_paid",
            existing_outstanding=1000.0,
            new_outstanding=1000.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 1
        assert anomalies[0].anomaly_type == "reappearance"
        assert anomalies[0].details["previous_status"] == "possibly_paid"
        assert anomalies[0].details["restored_to"] == "open"

    def test_non_possibly_paid_status_not_flagged_as_reappearance(self):
        for status in ["open", "promised", "disputed", "paused", "escalated"]:
            anomalies = detect_invoice_anomalies(
                invoice_id="inv-1",
                customer_id="cust-1",
                invoice_number="INV-001",
                existing_status=status,
                existing_outstanding=1000.0,
                new_outstanding=1000.0,
                existing_due_date=date(2026, 1, 15),
                new_due_date=date(2026, 1, 15),
            )
            assert all(a.anomaly_type != "reappearance" for a in anomalies), (
                f"Status '{status}' should not trigger reappearance"
            )

    def test_multiple_anomalies_on_same_invoice(self):
        """Balance increase + due date change + reappearance all at once."""
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="possibly_paid",
            existing_outstanding=1000.0,
            new_outstanding=2000.0,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 3, 15),
        )
        types = {a.anomaly_type for a in anomalies}
        assert types == {"balance_increase", "due_date_change", "reappearance"}

    def test_increase_rounding(self):
        anomalies = detect_invoice_anomalies(
            invoice_id="inv-1",
            customer_id="cust-1",
            invoice_number="INV-001",
            existing_status="open",
            existing_outstanding=99.99,
            new_outstanding=100.01,
            existing_due_date=date(2026, 1, 15),
            new_due_date=date(2026, 1, 15),
        )
        assert len(anomalies) == 1
        assert anomalies[0].details["increase"] == 0.02


class TestDetectCustomerAnomalies:
    def test_overdue_spike_flagged(self):
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=5,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" in types
        spike = next(a for a in anomalies if a.anomaly_type == "overdue_spike")
        assert spike.details["previous_overdue_count"] == 1
        assert spike.details["new_overdue_count"] == 5
        assert spike.details["delta"] == 4

    def test_overdue_spike_not_flagged_below_delta(self):
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=3,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" not in types

    def test_overdue_spike_not_flagged_below_floor(self):
        """Delta is 3 but post-count is only 3 (below floor of 4)."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=0,
            post_overdue_count=3,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" not in types

    def test_overdue_spike_at_exact_threshold(self):
        """Delta exactly 3, post-count exactly 4 — should flag."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=4,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" in types

    def test_overdue_spike_suppressed_for_new_customer(self):
        """Brand-new customer with many overdue invoices — no spike (no baseline)."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=0,
            post_overdue_count=5,
            is_new_customer=True,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" not in types

    def test_cluster_risk_flagged_on_threshold_crossing(self):
        """Customer crosses from below threshold to at-or-above."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=2,
            post_overdue_count=3,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "cluster_risk" in types
        cluster = next(a for a in anomalies if a.anomaly_type == "cluster_risk")
        assert cluster.details["overdue_invoice_count"] == 3

    def test_cluster_risk_not_flagged_when_already_above(self):
        """Customer was already above threshold — no re-fire."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=3,
            post_overdue_count=5,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "cluster_risk" not in types

    def test_cluster_risk_not_flagged_below_threshold(self):
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=2,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "cluster_risk" not in types

    def test_cluster_risk_flagged_for_new_customer(self):
        """New customer arriving with >= threshold overdue invoices is a valid crossing (0 -> N)."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=0,
            post_overdue_count=3,
            is_new_customer=True,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "cluster_risk" in types

    def test_spike_and_cluster_both_flagged(self):
        """Existing customer spikes from 1 to 5 — crosses cluster threshold AND spikes."""
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=5,
        )
        types = {a.anomaly_type for a in anomalies}
        assert "overdue_spike" in types
        assert "cluster_risk" in types

    def test_no_anomalies_when_stable_low(self):
        anomalies = detect_customer_anomalies(
            customer_id="cust-1",
            customer_name="Acme Ltd.",
            pre_overdue_count=1,
            post_overdue_count=1,
        )
        assert len(anomalies) == 0

    def test_customer_id_set_on_anomalies(self):
        anomalies = detect_customer_anomalies(
            customer_id="cust-abc",
            customer_name="Test Corp",
            pre_overdue_count=1,
            post_overdue_count=5,
        )
        for a in anomalies:
            assert a.customer_id == "cust-abc"
            assert a.invoice_id is None


class TestAnomalyToDict:
    def test_serialization(self):
        anomaly = Anomaly(
            anomaly_type="balance_increase",
            invoice_id="inv-1",
            customer_id="cust-1",
            details={"previous_amount": 100.0, "new_amount": 150.0},
        )
        d = anomaly_to_dict(anomaly)
        assert d["anomaly_type"] == "balance_increase"
        assert d["invoice_id"] == "inv-1"
        assert d["details"]["previous_amount"] == 100.0
