# BUILD LOG — Overdue Cash Control

> **Purpose:** Paste this file at the start of every AI session (Claude, Codex, GPT).
> It is the single source of operational truth. Read sections 1–5 first — they contain
> everything needed to resume work. Later sections are reference material.

## Identity

- **Product:** Overdue Cash Control — collections workflow for EU SMBs
- **Builder:** Lorenzo (founder, tester, decision-maker)
- **AI team:** Claude (architecture, prompt design, reviews) + GPT (senior reviewer) + Codex in VS Code (code writing, git). See decision #29 and `docs/ai-engineering-workflow.md`.
- **Stack:** Python/FastAPI backend, Next.js frontend, PostgreSQL on Railway, OpenAI + DeepSeek LLM, Resend email
- **Repo:** https://github.com/panda4505/overdue-cash-control

## Current State

- **Milestone:** 3 of 10 — IN PROGRESS
- **Sub-task:** M3-ST1 COMPLETE, M3-ST2 COMPLETE, M3-ST3 COMPLETE, M3-ST4 next
- **Status:** M3-ST3 (fuzzy customer matching) is done. 295 tests green (86 parser + 48 mapper + 15 ingestion + 10 upload + 10 webhooks + 24 normalization + 57 import commit + 12 imports router + 33 customer matching). Same-entity resolution with 6-step deterministic-first chain: exact name → merge_history alias → VAT ID → Jaro-Winkler (≥0.98) → user merge_decision → create new. Diacritic folding for comparison only. Trust-first: qualifier-based near-collisions require user confirmation. merge_history compounds value over time.
- **Latest validation:** Full backend 295/295. No regressions.
- **Blockers:** None
- **Last session:** 2026-03-22
- **Next:** M3-ST4 — framing pass, then anomaly detection

## Implementation Map

### Backend (`backend/app/`)

**FastAPI app** (`main.py`): Routes registered for webhooks, upload, import lifecycle (account-scoped upload + confirm). CORS configured for frontend. Health check at `/health`.

**Config** (`config.py`): pydantic-settings loading DATABASE_URL, TEST_DATABASE_URL, UPLOAD_DIR, OPENAI_API_KEY, DEEPSEEK_API_KEY, RESEND_API_KEY, RESEND_WEBHOOK_SECRET, SECRET_KEY, FRONTEND_URL.

**Database** (`database.py`): Async SQLAlchemy 2.0 engine + session factory. `Base` declarative base. `get_db()` dependency.

**Models** (`models/`): 7 models — Account, User, Customer, Invoice, ImportRecord, ImportTemplate, Activity. All registered in `__init__.py` for Alembic. Key schema facts:
- Invoice: 8 statuses (open/promised/disputed/paused/escalated/possibly_paid/recovered/closed), normalized_invoice_number for matching, data lineage fields (first_seen_import_id, last_updated_import_id), recovery tracking, 4 composite indexes
- Customer: normalized_name for matching, merge_history JSONB, soft delete, cached aggregates (total_outstanding, invoice_count)
- ImportRecord: change_set JSONB for rollback, scope_type (full_snapshot/partial/unknown), 4 invoice counters (created/updated/disappeared/unchanged), cost tracking
- Activity: flexible JSONB details, action_type enum-like string, 4 indexes

**File parser** (`services/file_parser.py`): CSV/XLSX parser. Encoding detection (chardet + Western European fallback with mojibake rejection). Delimiter detection. Header row detection. Format-shaped numeric/date type inference (4 number patterns, European-first). Pure-integer ID protection. `.xls` rejected.

**Column mapper** (`services/column_mapper.py`): 6-language deterministic dictionary (FR/IT/EN/CZ/DE/ES, ~150 aliases, 14 canonical fields). Template validation. Async LLM fallback with hallucination protection. Conflict resolution. Amount fallback logic.

**Ingestion pipeline** (`services/ingestion.py`): Canonical parse → map → preview pipeline. SHA-256 file hash. JSON-serializable sample rows. Used by both upload and email paths.

**Normalization** (`services/normalization.py`): `normalize_invoice_number()` strips separators, lowercases. `normalize_customer_name()` strips EU legal suffixes (CZ/SK/DE/FR/IT/ES/EN), NFC-normalizes, lowercases. Dotless legal suffixes added for Czech (`sro`), Italian (`srl`, `spa`), and Spanish (`sl`) markets.

**Import commit** (`services/import_commit.py`): Two-phase import lifecycle:
- `create_pending_import()`: parse + save file to disk + create ImportRecord(pending_preview). Gates on parse success, not mapping success. Duplicate hash warning.
- `confirm_import()`: Diff-aware reconciliation engine. Loads existing invoices by normalized_invoice_number. Classifies each file row as new/updated/unchanged. Disappeared invoices (absent from file) flagged as possibly_paid — **only when scope_type=full_snapshot**. Reappearing possibly_paid invoices always restored to open (even if data identical). Raw invoice_number immutable after first seen. Incoming-file duplicate and ambiguous existing-DB duplicate detection (warn-and-skip). Customer aggregates recalculated from DB post-loop (including reassigned invoice old customers). change_set tracks created/updated/disappeared for rollback. Per-invoice Activity for updated and disappeared. Customer resolution upgraded from exact-only to a deterministic-first chain: cache pre-check, then exact normalized name, merge_history alias reuse, VAT ID match, Jaro-Winkler ≥0.98 auto-merge with diacritic folding, user merge_decision for 0.70–0.98 range, else create new. merge_history reuse is deterministic (no duplicate events). In-memory matcher structures synced during row loop for same-import dedup and VAT backfill visibility. Fuzzy match preview in create_pending_import (best-effort).

**Customer matching** (`services/customer_matching.py`): Pure logic module, no DB dependency. `find_best_match()` shared by preview and confirm paths. `fold_diacritics()` for comparison-time accent stripping. `HIGH_THRESHOLD=0.98` (trust-first: only obvious typos auto-merge). `LOW_THRESHOLD=0.70` (below this, no match). Dataclasses: FileCustomer, ExistingCustomerInfo, MatchResult, FuzzyMatchResult.

**LLM client** (`services/llm_client.py`): OpenAI primary (gpt-4o-mini), DeepSeek fallback. Single async function. Provider-agnostic interface.

**Routers:**
- `routers/upload.py`: `POST /upload` — stateless preview (no DB write)
- `routers/imports.py`: `POST /accounts/{account_id}/imports/upload` — account-scoped pending import + preview. `POST /imports/{import_id}/confirm` — commit to DB. `ConfirmImportRequest` has Literal-validated scope_type and optional `merge_decisions` dict. Validated strictly — unknown customer IDs raise 400.
- `routers/webhooks.py`: Resend inbound email webhook. Downloads attachments, feeds into ingestion pipeline.

### Database

PostgreSQL 16 on Railway (managed). 2 Alembic migrations applied:
- `4a129036b96f`: initial 7 tables
- `7d3f8c2b1a90`: replace number_format with decimal_separator + thousands_separator on import_templates

### Test suite (295 tests)

- `test_file_parser.py` — 86 tests: 5 CSV + 1 XLSX fixture, encoding fallback, edge cases
- `test_column_mapper.py` — 48 tests: 6-language dictionary, template, LLM fallback, conflicts
- `test_ingestion.py` — 15 tests: all fixtures, hash, serialization, XLSX
- `test_upload.py` — 10 tests: CSV + XLSX upload, validation, response shape
- `test_webhooks.py` — 10 tests: parity tests, webhook endpoint coverage
- `test_normalization.py` — 24 tests: invoice number + customer name normalization, dotless suffixes
- `test_import_commit.py` — 57 tests: pending import, confirm lifecycle, mapping validation, TestDiffEngine (16 diff scenarios), TestFuzzyMerge (17 fuzzy matching scenarios)
- `test_imports_router.py` — 12 tests: upload/confirm endpoints, scope_type validation, merge_decisions contract
- `test_customer_matching.py` — 33 tests: fold_diacritics, merge_history, VAT, Jaro-Winkler, qualifier near-collision guards, typo positive regression, normalization integration
- DB tests require `TEST_DATABASE_URL` (must differ from `DATABASE_URL`). Per-test NullPool engine + TRUNCATE cleanup.

### Sample data (`sample-data/`)

6 synthetic AR export fixtures: pohoda (CZ/semicolon), fakturoid (EN/comma/EUR), messy_generic (CZ/messy), french (FR/semicolon/Windows-1252), italian (IT/semicolon/dot-comma), german (DE/XLSX/2 sheets).

### Frontend (`frontend/`)

Next.js 14 + Tailwind CSS + shadcn/ui. Landing page only. No functional UI yet (M4).

### Docs (`docs/`)

architecture.md, constitution.md, product-definition.md, trajectory.md, wedge-v1.md — product and architecture specs. Stable. Paste relevant sections when needed, not every session.

## Active Constraints

**Architectural invariants:**
- European-first compatibility. France and Italy are primary launch markets. Czech supported but not default.
- Upload-first ingestion. Manual upload is the guaranteed path. Email is a convenience wrapper.
- Preview-before-commit. Every import shows what will change before touching live data.
- Deterministic-first AI. Saved templates and rules primary. LLM is fallback only.
- confirm_import() is the single reconciliation/orchestration point for all import commits.

**M3-ST2 operational constraints (carry forward):**
- Disappeared invoices only flagged when scope_type == "full_snapshot"
- Raw invoice_number is immutable after first seen (normalized key is for matching)
- Reappearing possibly_paid invoices are always restored to open, even if data is otherwise identical
- Ambiguous existing DB duplicates (multiple invoices with same normalized number): warn-and-skip, not fail-fast
- Customer aggregates (total_outstanding, invoice_count) recalculated from DB, not incremental. Includes reassignment old customers. possibly_paid invoices remain in outstanding total until user confirms payment.
- Customer.last_invoice_date is NOT recalculated alongside aggregates — known staleness risk on disappearance/reassignment (deferred fix)

**Open bugs (active):**
- `routers/webhooks.py`: RESEND_WEBHOOK_SECRET exists in config but webhook does NOT verify signatures. Severity: High.
- `main.py`: `GET /test-email` is publicly reachable and hardcodes lorenzo.massimo.pandolfo@gmail.com. Severity: Medium.
- `routers/webhooks.py`: Inbound attachment bytes are not persisted to disk/object storage. Lost on failure or restart. Severity: Medium. Mitigation: email can be re-sent.

**Test infrastructure:**
- Codex sandbox has no PostgreSQL. DB-backed tests are run by Lorenzo locally.
- Python 3.12 for production (Dockerfile), 3.14.3 for local dev/test.
- Python 3.14 dependency warnings from OpenAI/Pydantic V1 and Starlette async — non-blocking, tracked.

## Current Milestone Exit Gate

> **Milestone 1: COMPLETE** — all 8/8 exit gates passed on 2026-03-20.
>
> **Milestone 2: COMPLETE** — all repo-level exit gates passed on 2026-03-21. 169 tests.
>
> **Milestone 3 is done when:**
> - [x] A second import to the same account correctly identifies new, updated, unchanged, and disappeared invoices
> - [x] Fuzzy customer matching merges obvious name variants and asks for confirmation on ambiguous ones
> - [ ] Anomalies are flagged (balance increase, due date change, reappeared invoice, cluster risk)
> - [x] No data lost or duplicated across sequential imports
>
> **M3-ST1 (first import commit path): COMPLETE** — 221 tests on 2026-03-22.
> **M3-ST2 (diff engine): COMPLETE** — 239 tests on 2026-03-22. TestDiffEngine 16/16, imports router 10/10, full backend 239/239. Prompt went through 3 review iterations (v1→v3) with GPT-5.4.

## Milestone History

### M1 — Infrastructure (sessions 1–3, 2026-03-19 to 2026-03-20)
- GitHub repo, Railway deploy (backend + frontend + PostgreSQL), Resend email (outbound + inbound webhook), Cloudflare DNS
- FastAPI scaffold, Next.js landing page, health check green
- 3 synthetic AR export fixtures (CZ, EN, CZ-messy) plus sample-data coverage notes for the ingestion engine
- Architecture doc, constitution, product definition, trajectory, wedge definition written
- Resend webhook + attachment lookup path debugged live; validation in this phase was manual rather than automated
- 0 automated tests. Validation was manual (live deploy, outbound email, webhook receipt).

### M2 — Ingestion Engine (sessions 4–9, 2026-03-20 to 2026-03-21)
- 7 SQLAlchemy models + 2 Alembic migrations
- Local dev stack standardized on SQLAlchemy 2.0.48 for Python 3.14 compatibility; Railway env/config updated for OpenAI, DeepSeek, and Resend
- File parser: CSV/XLSX, encoding detection with mojibake rejection, delimiter detection, header row detection, 4 number patterns
- Column mapper: 6-language dictionary, template validation, LLM fallback with hallucination protection
- Ingestion pipeline: canonical parse → map → preview, SHA-256 hash
- Upload endpoint (POST /upload) and email webhook wired to same pipeline
- Parity tests proving upload and email produce identical results
- 3 additional fixtures added (FR, IT, DE-XLSX)
- Cross-doc consistency pass aligned architecture/constitution/product/trajectory/wedge with the actual build and standardized the roadmap at 10 milestones
- 169 tests at M2 close

### M3 — Reconciliation & AI Layer (sessions 10–11, 2026-03-22) — IN PROGRESS
**ST1 (first import commit path):**
- Normalization service (invoice number + customer name, EU legal suffix stripping)
- Import commit service: create_pending_import() + confirm_import()
- Account-scoped import endpoints with mapping validation
- Customer deduplication, change_set for rollback, activity logging, audit fields
- DB test infrastructure (per-test NullPool engine, TRUNCATE cleanup, TEST_DATABASE_URL safety). Root cause of earlier failures was asyncpg connections crossing pytest event loops on Python 3.14.
- 221 tests at ST1 close

**ST2 (diff engine):**
- confirm_import() extended with diff-aware reconciliation
- Match by normalized_invoice_number within account
- Classify: new / updated / unchanged / disappeared
- Disappearance gated on scope_type=full_snapshot (Literal-validated at router)
- Reappearance from possibly_paid → open (even with identical data)
- Raw invoice_number immutable after first seen
- Incoming-file and existing-DB duplicate safety (warn-and-skip)
- Customer aggregates recalculated from DB (including reassignment old customers)
- Per-invoice Activity for updated and disappeared
- 3 prompt review iterations (v1→v3). Key fixes: scope_type gating, reappearance bug, duplicate safety, Literal validation, reassignment aggregates, ambiguity test coverage, router passthrough tests.
- Validation: TestDiffEngine 16/16, imports router 10/10, full backend 239/239. Environment setup issues resolved before final run.
- 239 tests at ST2 close

**ST3 (fuzzy customer matching):**
- Same-entity resolution implemented with a 6-step deterministic-first chain: exact normalized name, merge_history alias reuse, VAT ID, Jaro-Winkler ≥0.98 on diacritic-folded names, user merge_decision, else create new customer
- `services/customer_matching.py` added as a pure logic module shared by preview and confirm paths
- Dotless suffix normalization added for `sro`, `srl`, `spa`, and `sl`
- Trust-first thresholding locked with qualifier near-collision negative tests and typo positive regression tests
- `create_pending_import()` now returns best-effort fuzzy match preview; `ConfirmImportRequest` accepts optional `merge_decisions`
- Validation: full backend 295/295 with no regressions
- 295 tests at ST3 close

## Decisions Made

| # | Decision | Rationale | Date |
|---|----------|-----------|------|
| 1 | Python/FastAPI backend | Lorenzo's comfort language | 2026-03-19 |
| 2 | OpenAI primary, DeepSeek fallback | OpenAI for quality, DeepSeek for cost/redundancy | 2026-03-19 |
| 3 | ~~Postmark for inbound + outbound email~~ | Superseded by decision #8 (switched to Resend in session 2) | 2026-03-19 |
| 4 | Railway for all hosting | Zero DevOps, managed PostgreSQL | 2026-03-19 |
| 5 | Simple auth in M4, hardening in M8 | Email+password with bcrypt + JWT in M4 (Core UI). Auth hardening (verification, rate limiting, data isolation) in M8 (Security & Trust). | 2026-03-19 |
| 6 | Codex in VS Code for code writing | GPT-5.4, agent mode, direct file editing | 2026-03-19 |
| 7 | Next.js App Router frontend | Fastest path to a minimal web UI that can deploy cleanly alongside the FastAPI backend on Railway | 2026-03-19 |
| 8 | Switched email provider from Postmark to Resend | Faster path to a working inbound webhook and outbound test flow during Milestone 1; Resend was simpler to debug live on Railway | 2026-03-20 |
| 9 | Separated User from Account tables | Prevents painful migration when multi-user arrives post-launch; costs one extra table now vs risky data migration later | 2026-03-20 |
| 10 | SQLAlchemy 2.0.48 (upgraded from 2.0.36) | Python 3.14 compatibility — 2.0.36 had a Union type bug with 3.14 | 2026-03-20 |
| 11 | Soft deletes on Invoice and Customer | Financial data should never be hard-deleted; nullable deleted_at column | 2026-03-20 |
| 12 | JSONB for change_set, merge_history, activity details | Flexibility without creating dozens of tables; sufficient for v1, can normalize later if needed | 2026-03-20 |
| 13 | European-first compatibility is a project invariant | France and Italy are primary launch markets. Czech is supported but not the default reference case. Parser uses format-shaped detection (separator patterns, not country buckets). All fixtures, header dictionaries, and legal suffix handling must cover FR/IT as first-class. | 2026-03-21 |
| 14 | Python 3.12 for production (Dockerfile), 3.14.3 for local dev | Railway Dockerfile pins a Python 3.12 slim image for deployment stability. Local dev/test environment runs 3.14.3. Both are compatible — SQLAlchemy 2.0.48 upgrade (decision #10) resolved the only known incompatibility. No action needed unless a 3.14-only feature is used in code. | 2026-03-21 |
| 15 | Mojibake rejection guard in encoding detection | When trying single-byte encodings, reject any decode that produces C1 control characters (127–159) or known mojibake markers (¤©¹»¾). This forces the fallback chain to keep trying until clean text is found. Discovered when encoding proof tests showed Windows-1250 Czech decoded as ISO-8859-1 produced Č→È corruption. +9 lines in file_parser.py. | 2026-03-21 |
| 16 | Pending import gates on parse success, not mapping success | `IngestionResult.success` reflects mapping completeness, which is too strict for import creation. Users need to receive a preview even with imperfect mapping, fix it manually, then confirm. Pending imports are created whenever `file_hash` exists and `total_rows > 0`. Only true parse failures return `import_id=None`. | 2026-03-22 |
| 17 | Per-test NullPool engine for DB tests (no session-scoped engine) | Python 3.14 + asyncpg + pytest-asyncio creates each test function on its own event loop. A session-scoped engine's pooled connections are bound to the session loop and fail when used on a function loop (`RuntimeError: Future attached to a different loop`). Fix: each test creates its own engine with `NullPool`, runs `create_all` idempotently, truncates after. Trade-off: ~15min full suite vs seconds with savepoints, but correct on this stack. | 2026-03-22 |
| 18 | Mapping round-trips through client, not stored on ImportRecord | Preview returns the mapping; client sends it back on confirm. Server validates against actual file headers. Avoids premature schema changes. ImportTemplate persistence (saving confirmed mappings for reuse) is deferred to a later sub-task. | 2026-03-22 |
| 19 | Disappearance gated on scope_type=full_snapshot | Running disappearance unconditionally would flag every missing invoice on a partial export as "possibly paid." scope_type declared at confirm time via ConfirmImportRequest, default "unknown". Disappearance only fires when scope_type == "full_snapshot". Literal-validated — Pydantic 422 on invalid values. | 2026-03-22 |
| 20 | Raw invoice_number immutable after first seen | Normalized key is for matching; display string is the original formatting from the first import. Subsequent imports do not overwrite Invoice.invoice_number. | 2026-03-22 |
| 21 | Ambiguous DB duplicates: warn-and-skip, not fail-fast | If multiple existing invoices share the same normalized_invoice_number, the matching row is skipped with a warning rather than failing the entire import. Revisit when data-repair tooling exists. | 2026-03-22 |
| 22 | Customer aggregates recalculated from DB, not incremental | After the row loop, total_outstanding and invoice_count are recomputed by querying actual current invoices for all affected customers (including reassignment old customers). possibly_paid invoices remain in outstanding total. | 2026-03-22 |
| 23 | Same-entity resolution and relationship intelligence are architecturally separate | ST3 implements same-entity matching only: name variant dedup (Jaro-Winkler on diacritic-folded names), VAT ID dedup, confirmed alias memory (merge_history). Relationship intelligence (parent-subsidiary, group membership, commercial grouping) is a future capability requiring a separate model and UX, not an extension of merge_history. These must never be conflated. | 2026-03-22 |
| 24 | Diacritic folding is comparison-time only | fold_diacritics() strips accents for Jaro-Winkler comparison. Stored normalized_name and merge_history.normalized_name preserve accents. This ensures "Société Générale" and "Societe Generale" score 1.0 on JW without changing stored data. | 2026-03-22 |
| 25 | merge_history reuse is deterministic reuse, not a new merge | When a known alias is found in merge_history, it increments customers_reused only. No duplicate merge_history entry, no new customer_merged Activity, no change_set entry. Only first-time alias discovery (VAT, JW, user_confirmed) creates merge events. | 2026-03-22 |
| 26 | Auto-merge restricted to typo-like near-identity only (HIGH_THRESHOLD=0.98) | Qualifier-based near-collisions (country, branch, division, letter variants scoring 0.92–0.97) must not auto-merge. Deterministic paths (exact, VAT, merge_history) handle common cases at score 1.0. JW auto-merge at 0.98 catches only obvious single-char typos on longer names. Conservative first confirmation is acceptable because merge_history compounds value over time. Do not lower threshold without regression tests for both typo positives and near-collision negatives. | 2026-03-22 |
| 27 | Layered memory model | Repo uses layered memory: `BUILD_LOG.md` (concise operating memory / current state / decisions / queued items), `docs/opportunities.md` (strategic/commercial discoveries not yet committed), `docs/trajectory.md` (committed roadmap only). Opportunities stay out of trajectory until they get milestone ownership. | 2026-03-22 |
| 28 | Mandatory framing pass before each milestone and sub-task | Every new milestone and sub-task starts with a framing pass before implementation prompting. Framing must review: current BUILD_LOG state, completed-milestone learnings, relevant opportunities.md items, scope boundaries, invariants, risks, what is in scope vs deferred. No Codex prompt until framing is acceptable. | 2026-03-22 |
| 29 | Repo-frozen AI collaboration workflow | Repo uses explicit roles: Lorenzo (orchestrator/decider), Claude (architect/prompt writer), GPT (senior reviewer/challenger), Codex (implementer). Claude initiates, GPT reviews aggressively including framing. Full process documented in `docs/ai-engineering-workflow.md`. | 2026-03-22 |

## Queued Items

| Item | Target Milestone | Notes |
|------|-----------------|-------|
| Change Account defaults: currency CZK → EUR, timezone Europe/Prague → Europe/Paris | M4 (Core UI) | Onboarding should detect locale and suggest defaults |
| Update `company_id` comment from "IČO in Czech" to generic "company registration number" | Next schema pass | Cosmetic but signals correct mental model |
| Add Italian to required reminder template languages | M5 (Action Execution) | FR/IT are primary markets; Italian must be first-class |
| Rotate Railway PostgreSQL password | ASAP | Public URL with credentials used in terminal session during migration |
| File storage: replace local disk with object storage + encryption | Post-M3 | ST1 uses plain `UPLOAD_DIR` on local disk. Railway filesystem is ephemeral. Acceptable for dev, not production. |
| ImportTemplate persistence: save confirmed mappings for reuse | M3 or M4 | Currently mapping round-trips through client. Saving as template is a separate feature. |
| Optimize DB test runtime (~15min is slow) | Post-M3 | Per-test NullPool engine is correctness-first. Revisit faster isolation (e.g. pytest-asyncio loop scope config) when milestone pressure is lower. |
| Recompute Customer.last_invoice_date alongside aggregate recalculation | Post-M3 | ST2 recalculates total_outstanding and invoice_count but not last_invoice_date. After disappearance or reassignment, last_invoice_date on the old customer could reference an invoice no longer active there. Low severity for v1. |
| Tighten ambiguous-duplicate handling from warn-and-skip to fail-fast | Post data-repair tooling | Decision #21. Revisit when users have manual invoice merge/delete tooling. |
| Python 3.14 dependency warnings (OpenAI/Pydantic V1 internals, Starlette async) | Maintenance | Non-blocking. Observed during ST2 local validation. |
| Customer relationship/group intelligence | Post-M3 (likely M6+) | Separate from identity resolution. Likely requires CustomerGroup model with explicit membership, suggested-link workflow, and distinct UI. Not an extension of merge_history or fuzzy matching. See decision #23. |
| Multi-candidate fuzzy matching for user confirmation | Post-M3 | Current ST3 returns single best candidate per file customer. Future: return top N for richer confirmation UX. |
| docs/opportunities.md maintenance | Ongoing | Strategic/commercial opportunities discovered during build. Update when major product insights emerge. See docs/opportunities.md. |
| docs/ai-engineering-workflow.md maintenance | Ongoing | Update when workflow learnings emerge during build. |

## Infrastructure

| Service | Status | Notes |
|---------|--------|-------|
| GitHub | ✅ | https://github.com/panda4505/overdue-cash-control |
| Railway backend | ✅ | https://overdue-cash-control-production.up.railway.app |
| Railway frontend | ✅ | https://noble-possibility-production.up.railway.app |
| Railway PostgreSQL | ✅ | Attached to backend, /health reports db=connected |
| OpenAI + DeepSeek keys | ✅ | Configured in Railway env vars |
| Resend | ✅ | overduecash.com verified, inbound via tuaentoocl.resend.app |
| Cloudflare | ✅ | DNS for overduecash.com, auto-configured DKIM/SPF |

## Reference Docs

The full product spec lives in these docs (paste relevant sections when needed, not every session):
- **Docs map** (`docs/README.md`) — doc tiers, reading order, precedence rules, update decision matrix
- **AI engineering workflow** (`docs/ai-engineering-workflow.md`) — roles, review loop, framing pass, startup/close-out checklists
- **Opportunities** (`docs/opportunities.md`) — strategic/commercial discoveries not yet committed to roadmap
- **Product constitution** (`docs/constitution.md`) — governing principles, decision filter, beachhead definition, pricing, exclusions
- **Wedge definition v1** (`docs/wedge-v1.md`) — canonical wedge statement, scope boundary, input layer, AI role. Aligned with actual build.
- **Product definition** (`docs/product-definition.md`) — screen-by-screen UX, data model, ingestion/reconciliation/escalation engine specs. Aligned with actual build as of M2 start.
- **Build trajectory** (`docs/trajectory.md`) — 10 milestones, session plans, exit gates, risk register. Aligned with actual build as of M2 start.
- **Buyer analysis** — harsh buyer assessment with pricing signals, shared during M1 close-out

## For the AI: How to Use This File

### Reading priority
1. **Current State** — where we are, what's next
2. **Implementation Map** — what code exists and what it does
3. **Active Constraints and Open Bugs** — invariants and live issues
4. **Current Milestone Exit Gate** — what "done" looks like
5. Everything else is reference — consult when relevant

### Resuming work
- Read sections 1–5 before writing any code or prompts
- Check the exit gate to understand what the current milestone requires
- Check Active Constraints before proposing architecture changes
- Check Queued Items before adding something that's already tracked

### Updating this file
When Lorenzo says "update the build log" or "wrap up the session":
1. Update **Current State** (milestone, sub-task, status, test count, blockers, date, next)
2. Update **Implementation Map** if files were added or significantly changed (subsystem-level, not file-level)
3. Update **Active Constraints** if new invariants or operational rules were established
4. Update **Open Bugs** — add new ones, remove fixed ones
5. Update **Current Milestone Exit Gate** — check off completed items
6. Add a receipt block under the current milestone in **Milestone History** (what was built, test evidence, key decisions)
7. Append new decisions to **Decisions Made** (preserve numbering)
8. Append new deferred items to **Queued Items**

### Rules
- **Be concrete.** "Fixed parsing" is useless. "Fixed CSV parser choking on Windows-1250 — added mojibake rejection in file_parser.py" is useful.
- **Compress, don't narrate.** This file is AI operating memory, not a journal. Record facts, not stories.
- **Never delete decisions.** Decision numbering is stable across repo history.
- **Always include test evidence.** Every milestone receipt must state the test count and pass/fail.
- **Every Codex prompt that modifies files should end with** `git add . && git commit -m "..."`. Only add `&& git push origin main` when Lorenzo explicitly wants changes pushed without a manual diff review.
