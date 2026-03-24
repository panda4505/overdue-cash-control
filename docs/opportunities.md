# Opportunities — Strategic discoveries from build

> **Purpose:** Capture product, commercial, and architectural opportunities discovered during implementation. This file is strategic memory — not engineering spec, not BUILD_LOG operating state. Update when major insights emerge during build.
>
> **Graduation rule:** When an opportunity gets milestone ownership in `docs/trajectory.md`, it leaves this file and becomes roadmap.
>
> **Note:** Some items in this document are directional hypotheses inferred from implementation work, not validated market facts.

## How to use this file

- Review this file at the start of every milestone framing pass
- Review again at the start of each sub-task framing pass
- Use it to inform scope, not to silently expand scope
- If an item becomes relevant, explicitly decide whether it is: in current scope, deferred, or ready for roadmap graduation
- Once an opportunity gets milestone ownership in `docs/trajectory.md`, mark it as graduated or remove it
- This file is for strategic/product/commercial ideas, not detailed engineering TODOs

## Why this matters now

Entity resolution is becoming a core trust layer of the product. What started as "deduplicate customer names during import" has revealed a deeper value: **safe, intelligent resolution of messy customer identity data** — a recurring problem across many European SMB workflows and often handled poorly or inconsistently by typical AR tooling.

Customer trust depends on avoiding silent false-positive merges. A wrong merge corrupts exposure calculations, misdirects reminders, breaks audit trails, and erodes user confidence. The conservative-but-compounding approach (confirm once, remember forever) is both safer and stickier than aggressive auto-matching.

## Product direction emerging from ST3

The product is not just invoice ingestion and AR tracking. It is evolving toward **trusted messy-customer resolution for SMB finance workflows**. The matching pipeline built in ST3 — deterministic-first, conservative auto-merge, evidence-backed suggestions, confirmed alias memory — is the foundation.

Key insight: The design assumption is that deterministic paths (exact normalized name, VAT ID, previously confirmed alias) should cover the majority of routine safe matches, while heuristic matching is reserved for typo-like variants and user-reviewed ambiguity.

## Three-layer resolution model

### Layer A: Safe auto-merge (implemented in ST3)
- Exact normalized name (suffix-stripped, lowercased, accent-preserving)
- Exact VAT / tax registration ID
- Previously confirmed alias (merge_history)
- Jaro-Winkler ≥ 0.98 on diacritic-folded normalized names

### Layer B: Suggested match / manual confirmation (partially implemented in ST3)
- Typo-like variants below auto-merge threshold (0.70–0.98)
- Token additions or removals
- Qualifier differences (country, region, branch, division)
- Near-collisions that need human judgment
- **Next opportunity:** Multi-candidate review UX (currently returns single best candidate)

### Layer C: Relationship intelligence (not implemented — future)
- Parent / subsidiary detection
- Branch / country entity grouping
- Commercial group consolidation
- Contact-based relationship inference
- **Explicitly separate from same-entity merge logic** (BUILD_LOG decision #23)
- Likely requires a `CustomerGroup` model with explicit membership, suggested-link workflow, and distinct UI

## Immediate next-value opportunities

### Multi-candidate fuzzy review UX
- **What:** Return top N candidates per ambiguous match instead of single best. Let users see alternatives and pick the right one.
- **Why now:** The backend infrastructure exists (scoring, ranking). The gap is only in how many candidates are surfaced.
- **Impact:** Better confirmation accuracy → fewer false negatives → faster merge_history accumulation → smarter system.
- **Candidate window:** M4–M5 if prioritized.

### Matching confidence explanation
- **What:** Show users why a match was suggested (name similarity score, VAT match, merge_history hit). Make the system transparent.
- **Why:** Trust. Users who understand why a merge is suggested are more likely to confirm correct ones and reject incorrect ones.
- **Impact:** Higher confirmation quality. Differentiator against black-box competitors.

## Future identity-proofing / enrichment

Possible evidence sources for ambiguous candidate resolution (Layer B enhancement):
- VAT / tax ID validation against government registries
- Official company registry lookups (e.g., French SIRENE, Italian Camera di Commercio)
- Company identifiers (IČO, SIRET, Partita IVA)
- Address normalization and geocoding
- Website / domain / contact email evidence
- Legal-entity ownership datasets

This should be a future **evidence layer** that strengthens confidence in ambiguous matches — not a primary matching signal. The deterministic core (exact name, VAT, merge_history) remains the source of truth.

## Commercial story / moat

- **Positioning:** "Safe entity resolution under messy SMB data"
- **Mechanism:** Conservative but compounding intelligence. Each user confirmation makes the system permanently smarter for that account.
- **Trust posture:** False-positive merges are treated as more damaging than false negatives. The product errs on the side of asking.
- **Competitive advantage:** Most AR tools either don't deduplicate at all (manual mess) or auto-merge aggressively (dangerous). The middle ground — smart suggestions with human confirmation and permanent memory — is underserved.
- **Switching cost:** merge_history is account-specific learned intelligence that doesn't transfer to competitors.

## Guardrails

- Same-entity resolution and relationship intelligence must never be conflated (decision #23)
- Name similarity alone is not sufficient for broad silent auto-merge (decision #26)
- False-positive merges are more damaging than false negatives in a collections product
- merge_history is same-entity alias memory only — never for group/relationship data
- Threshold changes require regression tests for both typo positives and near-collision negatives

## Not for current milestone

These are captured here so they are not forgotten, but they are not in scope for M3:
- Relationship/group intelligence (candidate M6+ if prioritized)
- Multi-candidate review UX (candidate M4–M5 if prioritized)
- External registry validation (candidate M7+ if prioritized)
- Matching confidence explanation UI (candidate M5 if prioritized)
- Customer merge undo / unmerge tooling (post-M3)

## Import quality intelligence (CSV/XLSX paths)

> **Status:** Not committed. Fits current v1 input boundary (CSV/XLSX only).
> **Candidate timing:** M4–M7 if prioritized.

- **What:** Detect shaky imports even on structured CSV/XLSX paths. Flag abnormal skipped-row rates, duplicate rates, parse-fallback rates, low-confidence column mapping, and suspiciously uniform or empty columns.
- **Why:** Users import messy real-world files. The product should surface import-quality problems at preview time, not silently pass them through. This is ingestion/preview hardening — not reconciliation.
- **How:** Import quality metrics computed during `create_pending_import()` and surfaced in the preview response. Exact problematic rows/fields identified with recommended next action (re-export, fix source, review mapping).
- **Relationship to anomaly detection:** Import quality is about the health of the incoming file itself. Anomaly detection (M3-ST4) is about transitions in business data across imports. These are separate concerns.

## Low-confidence extraction / document rescue flow

> **Status:** Not committed. Contingent on expanding v1 input boundary beyond CSV/XLSX.
> **Dependency:** The current v1 boundary is CSV/XLSX structured exports only. PDF parsing is explicitly excluded. This opportunity becomes relevant only if/when the product expands to accept PDF, scanned, or OCR-processed inputs.
> **Candidate timing:** Post-v1 (v1.2+ at earliest).

- **What:** When the product accepts lower-quality inputs (PDF tables, scanned invoices, OCR output), use AI/OCR where reliable. Quarantine ambiguous rows/fields instead of silently committing them. Provide a pre-digested review/repair UX showing exact problem areas with recommended fixes.
- **Why:** SMBs often have messy source documents. If the product expands input types, it must handle quality gracefully rather than bluffing certainty.
- **Trust posture:** AI extracts aggressively where confidence is high. When confidence drops, the system narrows to the smallest manual review surface. Recommend better source files when appropriate. Aligns with constitution §5.9 (trust-calibrated automation).
- **Scope note:** This is NOT current v1 scope. Do not add PDF/OCR/scan UX to product-definition.md until the input boundary is explicitly expanded.

## Future anomaly families beyond M3-ST4

> **Status:** Not committed. M3-ST4 implemented the five foundational anomaly types.
> **Candidate timing:** M4–M7 depending on what pilot users surface.

Possible future anomaly categories beyond the five implemented in M3-ST4 (balance increase, due date change, reappearance, overdue spike, cluster risk):

- **Import-quality anomalies:** Abnormal parse failure rates, sudden column mapping changes, format shifts between imports, file-size anomalies.
- **Data-integrity anomalies:** Invoice number format changes, currency switches, customer name instability across imports, suspicious round-number patterns.
- **Identity anomalies:** Customers that keep generating merge candidates, high merge-history churn, potential false-positive merge patterns.
- **History/oscillation anomalies:** Invoices repeatedly disappearing and reappearing, balances oscillating, due dates repeatedly shifting.

These should be evaluated against the trust-calibrated automation doctrine: flag transitions that deserve human attention, suppress noise, and provide the narrowest possible review surface.

## Import trust screen as financial control checkpoint

> **Status:** Not committed. Foundation landing in M4-ST2.
> **Candidate timing:** M7–M9 (polish and commercial positioning).

- **What:** The import preview / business-diff screen is more than a "review before commit" step. It is a financial control checkpoint: nothing touches live receivables data without the operator seeing an explicit business-diff summary — what invoices are new, what changed, what disappeared, how much money is involved. This is a deliberate product trust boundary.
- **Why it matters commercially:** Most AR tools either auto-import silently (dangerous) or dump raw spreadsheets on the user (useless). A structured, money-quantified control checkpoint is a differentiated trust signal. It tells the buyer: "This product will never silently corrupt your receivables data." That promise is a wedge — especially for finance-cautious SMBs evaluating whether to trust a new tool with their cash position.
- **Future directions:** Per-invoice disposition on disappeared items (paid / credited / unknown). Anomaly drill-down with recommended actions. Import-over-import trend visibility (e.g., "your overdue total increased €12k since last import"). Recovery tracking tied to the control checkpoint.
- **Guardrail:** The trust screen must remain fast, scannable, and non-blocking for routine imports. Operator burden should scale with import risk, not import size.

## Skipped-row repair and guided import recovery

> **Status:** Not committed. Precursor signals landing in M4-ST2 (skipped_rows + warnings).
> **Candidate timing:** M5–M7 if prioritized.

- **What:** Rows skipped during import (missing fields, invalid dates, duplicate invoice numbers, ambiguous DB matches) should become a recoverable operator workflow, not just warning noise. The product should explain why each row was skipped, guide the operator toward a fix (correct the source file, manually enter the row, resolve the ambiguity), and potentially support targeted retry or re-import of just the failed rows.
- **Why:** Skipped rows are silent data loss from the operator's perspective. A file with 200 rows and 8 skipped means 8 invoices the operator thinks are tracked but aren't. Over multiple imports, this erodes trust and creates blind spots in the receivables picture — exactly the problem the product exists to solve.
- **Future directions:** Skipped-row detail panel with per-row explanation and suggested fix. "Fix and retry" flow for correctable issues (e.g., missing due date that the operator can supply manually). Import health score based on skip rate trend across imports. Proactive warning when a file's skip rate exceeds historical baseline.
- **Relationship to import quality intelligence:** Import quality (see above) flags file-level health issues; skipped-row repair addresses row-level recovery. These are complementary but distinct.
