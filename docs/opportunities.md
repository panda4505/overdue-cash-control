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
