"""Anomaly detection — deterministic rules for import-time anomaly flagging.

Pure logic module. No database imports. Fully unit-testable without Postgres.
Called by import_commit.confirm_import() during the row loop (invoice-level)
and after the row loop (customer-level).
"""

from __future__ import annotations

import dataclasses
from datetime import date
from typing import Any


# --- Thresholds ---
# All anomalies are differential: they flag a transition detected during
# this specific import, not a standing condition.

# Overdue spike: flag when a customer's overdue count jumps by >= this delta
OVERDUE_SPIKE_DELTA = 3
# Overdue spike: AND post-import overdue count must be >= this floor
OVERDUE_SPIKE_FLOOR = 4
# Cluster risk: flag when a customer *crosses into* this many open overdue invoices
# (pre < threshold AND post >= threshold). Does NOT re-fire while above threshold.
CLUSTER_RISK_THRESHOLD = 3


@dataclasses.dataclass
class Anomaly:
    """A single detected anomaly."""

    anomaly_type: str  # balance_increase | due_date_change | reappearance | overdue_spike | cluster_risk
    invoice_id: str | None  # UUID string, or None for customer-level anomalies
    customer_id: str | None  # UUID string
    details: dict[str, Any]


def detect_invoice_anomalies(
    *,
    invoice_id: str,
    customer_id: str,
    invoice_number: str,
    existing_status: str,
    existing_outstanding: float,
    new_outstanding: float,
    existing_due_date: date | None,
    new_due_date: date | None,
) -> list[Anomaly]:
    """Detect per-invoice anomalies by comparing existing DB state to incoming file data.

    Called for every existing invoice that appears in the import file.
    Returns zero or more anomalies — multiple anomalies per invoice are allowed.
    """

    anomalies: list[Anomaly] = []

    # Balance increase (not decrease — decreases are normal partial payments)
    if new_outstanding > existing_outstanding:
        anomalies.append(
            Anomaly(
                anomaly_type="balance_increase",
                invoice_id=invoice_id,
                customer_id=customer_id,
                details={
                    "invoice_number": invoice_number,
                    "previous_amount": existing_outstanding,
                    "new_amount": new_outstanding,
                    "increase": round(new_outstanding - existing_outstanding, 2),
                },
            )
        )

    # Due date change (any change — both forward and backward are noteworthy)
    if (
        existing_due_date is not None
        and new_due_date is not None
        and existing_due_date != new_due_date
    ):
        anomalies.append(
            Anomaly(
                anomaly_type="due_date_change",
                invoice_id=invoice_id,
                customer_id=customer_id,
                details={
                    "invoice_number": invoice_number,
                    "previous_due_date": existing_due_date.isoformat(),
                    "new_due_date": new_due_date.isoformat(),
                },
            )
        )

    # Reappearance: invoice was possibly_paid but showed up again in the file
    if existing_status == "possibly_paid":
        anomalies.append(
            Anomaly(
                anomaly_type="reappearance",
                invoice_id=invoice_id,
                customer_id=customer_id,
                details={
                    "invoice_number": invoice_number,
                    "previous_status": existing_status,
                    "restored_to": "open",
                },
            )
        )

    return anomalies


def detect_customer_anomalies(
    *,
    customer_id: str,
    customer_name: str,
    pre_overdue_count: int,
    post_overdue_count: int,
    is_new_customer: bool = False,
    overdue_spike_delta: int = OVERDUE_SPIKE_DELTA,
    overdue_spike_floor: int = OVERDUE_SPIKE_FLOOR,
    cluster_risk_threshold: int = CLUSTER_RISK_THRESHOLD,
) -> list[Anomaly]:
    """Detect customer-level anomalies after the import row loop completes.

    Called once per affected customer after customer aggregates are recalculated.
    All anomalies are differential — they flag transitions, not standing conditions.

    Overdue spike: post - pre >= delta AND post >= floor.
      Suppressed for customers first created in this import (no baseline to spike from).
    Cluster risk: pre < threshold AND post >= threshold (threshold-crossing only).
      Does NOT re-fire while the customer remains above threshold.
    """

    anomalies: list[Anomaly] = []

    # Overdue spike — suppressed for brand-new customers (no prior baseline)
    if not is_new_customer:
        delta = post_overdue_count - pre_overdue_count
        if delta >= overdue_spike_delta and post_overdue_count >= overdue_spike_floor:
            anomalies.append(
                Anomaly(
                    anomaly_type="overdue_spike",
                    invoice_id=None,
                    customer_id=customer_id,
                    details={
                        "customer_name": customer_name,
                        "previous_overdue_count": pre_overdue_count,
                        "new_overdue_count": post_overdue_count,
                        "delta": delta,
                    },
                )
            )

    # Cluster risk — threshold-crossing only (not repeated while above)
    if (
        pre_overdue_count < cluster_risk_threshold
        and post_overdue_count >= cluster_risk_threshold
    ):
        anomalies.append(
            Anomaly(
                anomaly_type="cluster_risk",
                invoice_id=None,
                customer_id=customer_id,
                details={
                    "customer_name": customer_name,
                    "overdue_invoice_count": post_overdue_count,
                },
            )
        )

    return anomalies


def anomaly_to_dict(anomaly: Anomaly) -> dict[str, Any]:
    """Serialize an Anomaly to a JSON-compatible dict."""
    return dataclasses.asdict(anomaly)
