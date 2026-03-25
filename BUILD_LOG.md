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

- **Milestone:** 4 of 10 — IN PROGRESS
- **Sub-task:** M4-ST3 COMPLETE. M4-ST2 COMPLETE. M4-ST1 (Part 1 backend + Part 2 frontend) COMPLETE.
- **Status:** Backend 398 tests green (378 existing + 20 dashboard). Frontend: tsc + build green.
- **Latest validation:** Dashboard endpoint verified: backend import OK, 20 dashboard tests passed (empty state, aging boundaries, reconciliation invariant, live date math proof, possibly_paid inclusion, account isolation, soft deletes, stale threshold, feed filtering, subset scoping), frontend tsc + build green.
- **Blockers:** None
- **Last session:** 2026-03-24
- **Next:** M4-ST4 — Action queue. Framing pass required.

## Implementation Map

### Backend (`backend/app/`)

**FastAPI app** (`main.py`): Routes registered for auth, webhooks, upload, import lifecycle (account-scoped upload + save-template + confirm), dashboard. CORS configured for frontend. Health check at `/health`. Version 0.2.0. `/test-email` removed.

**Auth** (`routers/auth.py`, `services/auth.py`, `dependencies.py`): Register (email+password only, company_name deferred to onboarding), login, me, update account. Email normalized (trim+lowercase). bcrypt hashing via passlib. JWT via python-jose. `get_current_user` dependency on all protected routes. Account isolation: `current_user.account_id` validated on all account-scoped endpoints.

**Template service** (`services/template_service.py`): Save template via explicit endpoint (idempotent per import — repeated calls update, not duplicate). Find matching template for auto-apply (exact normalized header-set match + delimiter/decimal compatibility + exactly-one-candidate rule). Linked to ImportRecord via template_id.

**Config** (`config.py`): pydantic-settings loading DATABASE_URL, TEST_DATABASE_URL, UPLOAD_DIR, OPENAI_API_KEY, DEEPSEEK_API_KEY, RESEND_API_KEY, RESEND_WEBHOOK_SECRET, SECRET_KEY, FRONTEND_URL.

**Database** (`database.py`): Async SQLAlchemy 2.0 engine + session factory. `Base` declarative base. `get_db()` dependency.

**Models** (`models/`): 7 models — Account, User, Customer, Invoice, ImportRecord, ImportTemplate, Activity. All registered in `__init__.py` for Alembic. Key schema facts:
- Invoice: 8 statuses (open/promised/disputed/paused/escalated/possibly_paid/recovered/closed), normalized_invoice_number for matching, data lineage fields (first_seen_import_id, last_updated_import_id), recovery tracking, 4 composite indexes
- Customer: normalized_name for matching, merge_history JSONB, soft delete, cached aggregates (total_outstanding, invoice_count)
- ImportRecord: change_set JSONB for rollback, scope_type (full_snapshot/partial/unknown), 4 invoice counters (created/updated/disappeared/unchanged), skipped_rows (renamed from errors in M4-ST2), cost tracking
- Activity: flexible JSONB details, action_type enum-like string, 4 indexes

**File parser** (`services/file_parser.py`): CSV/XLSX parser. Encoding detection (chardet + Western European fallback with mojibake rejection). Delimiter detection. Header row detection. Format-shaped numeric/date type inference (4 number patterns, European-first). Pure-integer ID protection. `.xls` rejected.

**Column mapper** (`services/column_mapper.py`): 6-language deterministic dictionary (FR/IT/EN/CZ/DE/ES, ~150 aliases, 14 canonical fields). Template validation. Async LLM fallback with hallucination protection. Conflict resolution. Amount fallback logic.

**Ingestion pipeline** (`services/ingestion.py`): Canonical parse → map → preview pipeline. SHA-256 file hash. JSON-serializable sample rows. Used by both upload and email paths.

**Normalization** (`services/normalization.py`): `normalize_invoice_number()` strips separators, lowercases. `normalize_customer_name()` strips EU legal suffixes (CZ/SK/DE/FR/IT/ES/EN), NFC-normalizes, lowercases. Dotless legal suffixes added for Czech (`sro`), Italian (`srl`, `spa`), and Spanish (`sl`) markets.

**Import commit** (`services/import_commit.py`): Shared-planner import architecture with preview/confirm parity:
- `create_pending_import()`: parse + save file to disk + create ImportRecord(pending_preview). Gates on parse success, not mapping success. Duplicate hash warning.
- `prepare_import_context()`: Shared preparation for preview and confirm. Loads ImportRecord, reparses file, validates mapping, loads existing invoices/customers, builds indexed lookup maps, converts ORM objects to frozen snapshot dataclasses, resolves merge_decisions. Returns ImportContext. Both preview and confirm call this — no duplicated preparation logic.
- `build_import_plan()`: Pure classification on immutable snapshots. No ORM, no DB, no mutations. Iterates canonical rows, classifies each as new/updated/unchanged. Resolves customers via deterministic chain. Detects disappearances (scope_type=full_snapshot only). Computes invoice-level and customer-level anomalies in-memory. Returns ImportPlan dataclass. Both preview and confirm call this — no duplicated classification logic.
- `preview_import()`: Calls prepare + plan, serializes to structured preview response with preview_generated_at timestamp. Zero DB mutations.
- `_apply_import_plan()`: Applies an ImportPlan to the database. Creates customers/invoices from plan data, updates existing ORM objects, writes Activities, builds change_set. Uses resolve_customer_ref() to map placeholder IDs to real customer IDs — never re-runs matching or re-derives customer identity from display names.
- `confirm_import()`: Calls prepare + plan + apply + commit. Returns summary response derived from the plan.
- Preview anomaly serialization uses an explicit safe-detail allowlist (PREVIEW_ANOMALY_SAFE_DETAIL_KEYS) — placeholder IDs and internal identifiers are never exposed in the preview API response.

**Customer matching** (`services/customer_matching.py`): Pure logic module, no DB dependency. `find_best_match()` shared by preview and confirm paths. `fold_diacritics()` for comparison-time accent stripping. `HIGH_THRESHOLD=0.98` (trust-first: only obvious typos auto-merge). `LOW_THRESHOLD=0.70` (below this, no match). Dataclasses: FileCustomer, ExistingCustomerInfo, MatchResult, FuzzyMatchResult.

**Anomaly detection** (`services/anomaly_detection.py`): Pure logic module, no DB dependency. `detect_invoice_anomalies()` for per-invoice checks (balance increase, due date change, reappearance from possibly_paid). `detect_customer_anomalies()` for post-loop checks (overdue spike, cluster risk). All anomalies are differential — flag transitions, not standing conditions. Thresholds: overdue spike delta ≥ 3 AND post-count ≥ 4, cluster risk ≥ 3 open overdue (threshold-crossing only). Spike suppressed for customers created in current import.

**LLM client** (`services/llm_client.py`): OpenAI primary (gpt-4o-mini), DeepSeek fallback. Single async function. Provider-agnostic interface.

**Routers:**
- `routers/upload.py`: `POST /upload` — auth-protected stateless preview (no DB write)
- `routers/imports.py`: `POST /accounts/{account_id}/imports/upload` — account-scoped pending import + preview. `POST /imports/{import_id}/save-template` — persist confirmed mapping for reuse. `POST /imports/{import_id}/preview-diff` — business diff preview (structured plan without DB commit). `POST /imports/{import_id}/confirm` — commit to DB. `ConfirmImportRequest` has Literal-validated scope_type and optional `merge_decisions` dict. Both preview-diff and confirm use the same request body. Validated strictly — unknown customer IDs raise 400.
- `routers/webhooks.py`: Resend inbound email webhook. Downloads attachments, feeds into ingestion pipeline.
- `routers/dashboard.py`: `GET /dashboard` — read-only dashboard endpoint returning complete overdue picture. Typed Pydantic response (DashboardResponse). All calculations use live date math (CURRENT_DATE - due_date), never stored days_overdue. Total overdue includes possibly_paid (BUILD_LOG doctrine). Disputed and possibly_paid counts scoped as overdue subsets (due_date < today). Aging buckets: Current (not yet due), 1–7, 8–30, 31–60, 60+ days. Top exposure customer. Recent changes feed with overfetch→filter→trim (50 candidates, 15 returned). Stale-data indicator (last_import_at > 24h). Amount serialization: fixed 2-decimal strings.

### Database

PostgreSQL 16 on Railway (managed). 4 Alembic migrations in repo:
- `4a129036b96f`: initial 7 tables
- `7d3f8c2b1a90`: replace number_format with decimal_separator + thousands_separator on import_templates
- `a1b2c3d4e5f6`: company_name nullable, existing accounts updated to EUR/Europe/Paris
- `8a7266974e1b`: rename errors to skipped_rows on import_records

### Test suite (398 tests)

- `test_file_parser.py` — 86 tests: 5 CSV + 1 XLSX fixture, encoding fallback, edge cases
- `test_column_mapper.py` — 48 tests: 6-language dictionary, template, LLM fallback, conflicts
- `test_ingestion.py` — 15 tests: all fixtures, hash, serialization, XLSX
- `test_upload.py` — 10 tests: CSV + XLSX upload, validation, response shape
- `test_webhooks.py` — 10 tests: parity tests, webhook endpoint coverage
- `test_normalization.py` — 24 tests: invoice number + customer name normalization, dotless suffixes
- `test_import_commit.py` — 77 tests: pending import, confirm lifecycle, mapping validation, TestPreviewImport (5 preview tests: first-import-all-new, no-DB-mutation, subsequent-import-with-changes, parity-with-confirm, detects-anomalies), TestDiffEngine (16 diff scenarios), TestFuzzyMerge (17 fuzzy matching scenarios), TestAnomalyDetection (15 anomaly integration scenarios)
- `test_imports_router.py` — 15 tests: upload/confirm/preview-diff endpoints, scope_type validation, merge_decisions contract
- `test_customer_matching.py` — 33 tests: fold_diacritics, merge_history, VAT, Jaro-Winkler, qualifier near-collision guards, typo positive regression, normalization integration
- `test_anomaly_detection.py` — 23 tests: pure logic module coverage for 5 anomaly types, thresholds, suppression rules, and serialization
- `test_auth.py` — 22 tests: register/login/me/update account, protected routes, account isolation, `/test-email` removal
- `test_auth_service.py` — 9 tests: password hashing and JWT token helpers
- `test_template_service.py` — 6 tests: save-template persistence, idempotency, wrong-account protection, strict auto-apply
- `test_dashboard.py` — 20 tests: empty state, overdue totals with possibly_paid inclusion, aging bucket boundaries (8 boundary dates), aging reconciliation (overdue buckets sum == total_overdue), live date math proof (stale days_overdue=999 ignored), top exposure correct customer, top exposure null when no overdue, disputed/possibly_paid as overdue subsets (not-yet-due excluded), account isolation, soft delete exclusion, stale threshold, recent changes filtering and descriptions, last import ordering, recovered/closed exclusion, current bucket not-yet-due inclusion
- DB tests require `TEST_DATABASE_URL` (must differ from `DATABASE_URL`). Per-test NullPool engine + TRUNCATE cleanup.

### Sample data (`sample-data/`)

6 synthetic AR export fixtures: pohoda (CZ/semicolon), fakturoid (EN/comma/EUR), messy_generic (CZ/messy), french (FR/semicolon/Windows-1252), italian (IT/semicolon/dot-comma), german (DE/XLSX/2 sheets).

### Frontend (`frontend/`)

Next.js 14 + Tailwind CSS 3 + shadcn/ui v3 (New York, Zinc, HSL CSS variables) + sonner. Shared API client with explicit auth mode (required/none), scoped 401 handling. Auth context provider with resilient fetchMe. Login, register, onboarding, protected layout with sidebar nav. Import flow: upload → column mapping (14 canonical target fields, client-side validation mirroring backend rules) → fuzzy match decisions → trust screen (business diff preview with summary cards, expandable detail sections, customer resolution visibility, anomaly display, template save) → confirm. Dashboard: summary cards (total overdue, overdue today, disputes open, payment review), wow-moment narrative strip, aging breakdown table, recent changes feed, last import footer, stale-data warning. Empty state for no-import accounts. Post-login routing based on company_name null check. shadcn Table component added for dashboard aging breakdown.

### Docs (`docs/`)

architecture.md, constitution.md, product-definition.md, trajectory.md, wedge-v1.md — product and architecture specs. Stable. Paste relevant sections when needed, not every session.

## Active Constraints

**Architectural invariants:**
- European-first compatibility. France and Italy are primary launch markets. Czech supported but not default.
- Upload-first ingestion. Manual upload is the guaranteed path. Email is a convenience wrapper.
- Preview-before-commit. Every import shows what will change before touching live data.
- Deterministic-first AI. Saved templates and rules primary. LLM is fallback only.
- confirm_import() is the single reconciliation/orchestration point for all import commits.
- Preview/confirm parity through shared planner. preview_import() and confirm_import() share the same prepare_import_context() and build_import_plan() code paths. The planner operates on frozen snapshot dataclasses, not ORM objects. This is the approved architecture for business-diff preview before commit.

**M3-ST2 operational constraints (carry forward):**
- Disappeared invoices only flagged when scope_type == "full_snapshot"
- Raw invoice_number is immutable after first seen (normalized key is for matching)
- Reappearing possibly_paid invoices are always restored to open, even if data is otherwise identical
- Ambiguous existing DB duplicates (multiple invoices with same normalized number): warn-and-skip, not fail-fast
- Customer aggregates (total_outstanding, invoice_count) recalculated from DB, not incremental. Includes reassignment old customers. possibly_paid invoices remain in outstanding total until user confirms payment.
- Customer.last_invoice_date is NOT recalculated alongside aggregates — known staleness risk on disappearance/reassignment (deferred fix)

**M4-ST3 dashboard invariants (carry forward):**
- All overdue/aging calculations use live date math (CURRENT_DATE - due_date), never stored Invoice.days_overdue (which is only updated during import commits and becomes stale between imports)
- Total overdue includes possibly_paid. Payment Review card shows possibly_paid count as a flagged overdue subset.
- Disputed and possibly_paid counts are overdue subsets: both require due_date < today
- Aging buckets: Current (not yet due), 1–7, 8–30, 31–60, 60+ days. SUM(overdue buckets) == total_overdue_amount. Current bucket excluded from overdue sum.
- Amount serialization: all Decimal money fields → fixed 2-decimal strings ("0.00", "2500.00")

**Open bugs (active):**
- `routers/webhooks.py`: RESEND_WEBHOOK_SECRET exists in config but webhook does NOT verify signatures. Severity: High. Explicitly deferred from M4-ST1 — will be addressed in a dedicated sub-task.
- ~~`main.py`: `GET /test-email` is publicly reachable~~ — RESOLVED in M4-ST1 Part 1. Endpoint deleted.
- `routers/webhooks.py`: Inbound attachment bytes are not persisted to disk/object storage. Lost on failure or restart. Severity: Medium. Mitigation: email can be re-sent.

**Test infrastructure:**
- Codex sandbox has no PostgreSQL. DB-backed tests are run by Lorenzo locally.
- Python 3.12 for production (Dockerfile), 3.14.3 for local dev/test.
- Python 3.14 dependency warnings from OpenAI/Pydantic V1 and Starlette async — non-blocking, tracked.
- Local Python/Alembic commands from `backend/` require `PYTHONPATH=.` for module resolution: `PYTHONPATH=. python -m pytest tests/ -v`, `PYTHONPATH=. alembic upgrade head`. Without it, Python cannot find the `app` module. Discovered during M4-ST1 verification.
- Test DB (occ_test) requires Alembic migrations applied separately. `create_all` from test fixtures creates tables but does NOT alter existing columns, and if tests have already populated a fresh test DB before Alembic versioning exists, `alembic upgrade head` can fail with duplicate-table errors. Safe path: recreate the test DB (or stamp it appropriately if preserving an existing schema), then run `DATABASE_URL=<TEST_DB_URL> PYTHONPATH=. alembic upgrade head` before the full DB-backed suite. Discovered during M4-ST1 verification when the nullable `company_name` migration had not been applied to occ_test.
- bcrypt pinned to 4.1.3 in requirements.txt. passlib 1.7.4 is incompatible with bcrypt 5.x on Python 3.14 (runtime crash during auth init). Discovered during Codex verification.

## Current Milestone Exit Gate

> **Milestone 1: COMPLETE** — all 8/8 exit gates passed on 2026-03-20.
>
> **Milestone 2: COMPLETE** — all repo-level exit gates passed on 2026-03-21. 169 tests.
>
> **Milestone 3: COMPLETE** — all 4/4 exit gates passed on 2026-03-22. 333 tests.
>
> **Milestone 4 is done when:**
> - [x] Dashboard shows current overdue picture at a glance
> - [ ] Action queue displays prioritized work items
> - [ ] Invoice and customer detail views are functional
> - [x] Auth (email+password, bcrypt, JWT) protects all routes
> - [x] Import flow accessible from the UI with trust screen (upload, mapping, fuzzy decisions, business diff preview, confirm)

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

### M3 — Reconciliation & AI Layer (sessions 10–11, 2026-03-22) — COMPLETE
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

**ST4 (anomaly detection):**
- Pure logic module `services/anomaly_detection.py` — no DB imports, same pattern as customer_matching
- 5 differential anomaly types: balance_increase, due_date_change, reappearance (possibly_paid only), overdue_spike, cluster_risk
- Invoice-level anomalies detected during row loop before status mutation; customer-level anomalies detected post-loop with pre/post overdue snapshot
- Overdue spike suppressed for customers first created in current import (no baseline to spike from)
- Cluster risk is threshold-crossing only (pre < 3 AND post >= 3) — does not re-fire while above threshold
- Activity records (action_type=anomaly_flagged), change_set["anomalies"], confirm response enriched
- Validation: full backend 333/333 (295 + 23 unit + 15 integration). Zero regressions.
- 333 tests at M3 close

**M3 close-out (docs consolidation):**
- Constitution §5.9 tightened from "AI is subordinate" to trust-calibrated automation doctrine
- Repo-wide AI-role drift corrected: wedge (8 locations), architecture stack table, product-definition heading — diff engine, anomaly flagging, and fuzzy matching are deterministic, not AI
- Architecture gained design principle #7 (trust-calibrated automation)
- Workflow close-out checklist gained insight-routing guidance
- Opportunities gained 3 new structured entries (import quality intelligence, document rescue flow, future anomaly families)
- Low-confidence document handling discussed and intentionally deferred (belongs to ingestion hardening, contingent on input-boundary expansion beyond CSV/XLSX)

### M4 — Core UI (sessions starting 2026-03-23)

**ST1 Part 1 (backend auth + template service + API hardening):**
- Auth: register (email+password only), login, me, update account (onboarding). Email normalized. JWT via python-jose + bcrypt via passlib.
- Account isolation: `get_current_user` dependency validates `current_user.account_id` on all account-scoped routes. Basic tenant isolation in M4; broader hardening remains M8.
- Template persistence: `POST /imports/{id}/save-template` — idempotent per import. Explicit endpoint call (not automatic); frontend calls it when user confirms mapping. Preserves mapping work even if import is later cancelled.
- Template auto-apply: exact normalized header-set match + delimiter/decimal compatibility + exactly-one-candidate rule. Intentionally strict.
- All endpoints auth-protected except `/health`, `/`, `/auth/*`, `/webhooks/*`.
- `/test-email` deleted. Account defaults: EUR, Europe/Paris. company_name nullable (set during onboarding).
- Alembic migration `a1b2c3d4e5f6`: company_name nullable, existing accounts updated to EUR/Europe/Paris.
- `import_commit.py`: `create_pending_import()` accepts `template_mapping` param, passes through to `ingest_file` as `existing_template`.
- Verification fix: `tests/test_import_commit.py` fake_ingest_file mock signature updated to accept `existing_template` kwarg (stale mock from pre-ST1 signature).
- ST1 preview contract: parse/mapping preview only (IngestionResult + duplicate warning + fuzzy matches). Business diff preview (new/updated/disappeared/anomalies) deferred to M4-ST2.
- Validation: full backend 370/370 locally. Zero regressions. Two commits: main ST1 slice + mock signature fix.
- 370 tests at ST1 Part 1 close

**ST1 Part 2 (frontend auth + onboarding + import mapping flow):**
- App shell: protected layout, sidebar nav, auth-gated routing
- Auth: shared API client with explicit auth mode (required/none), scoped 401 handling, session-expired toast. Login/register use auth:"none" so backend errors surface directly. fetchMe resilient to transient errors.
- Onboarding: company_name → PATCH /auth/account → /imports/new
- Import flow: upload (CSV/TSV/XLSX) → mapping (14 canonical fields, required-field + duplicate-source validation) → fuzzy decisions (auto_merges informational, candidates actionable) → review → optional save-template → confirm → dashboard
- Mapping transforms preview array to { target_field: source_column } dict
- Handles null/absent fuzzy_matches, null import_id, optional applied_template, null resend_inbound_address
- shadcn v4 / Tailwind 3 incompatibility: initial commit (04f07cc) used shadcn@latest which pulled v4. npm run build failed. Repair commit (388b293) replaced v4 with manual shadcn v3 components. No business logic changes in repair.
- Validation: tsc + build passing. Browser smoke test passed end-to-end.
- 370 backend tests unchanged (backend frozen for Part 2)

**ST2 (business diff preview + trust screen):**
- Shared-planner architecture: prepare_import_context() (shared preparation) + build_import_plan() (immutable, pure classification on frozen dataclasses) + preview_import() / confirm_import() both using the same prep+plan path
- POST /imports/{id}/preview-diff endpoint returning structured diff: per-invoice line items for created/updated/disappeared, money totals, anomalies with sanitized details, customer resolution trust signals
- _apply_import_plan() applies plan to DB without re-running matching. resolve_customer_ref() maps placeholder IDs to real customer IDs at commit time.
- Frontend step 4 converted from metadata-only to trust screen: summary cards (counts + money totals), 5 expandable detail sections (new invoices, updated, no-longer-in-file, anomalies, customer resolutions), skipped-rows warning, duplicate warning, metadata footer. Template save preserved.
- Alembic migration: errors renamed to skipped_rows on ImportRecord for semantic clarity
- Preview anomaly serialization uses explicit safe-detail allowlist — no placeholder IDs or internal identifiers leak to the API
- 4 GPT senior review iterations on framing (v1→v3-final). Key corrections: replaced rollback-based dry-run with shared planner architecture, added immutable snapshot boundary, tightened planner/apply identity contract, sanitized anomaly serialization, strengthened parity test assertions.
- Malformed-source CSV incident during browser smoke testing (Expected 15 fields in line 8, saw 16): correct parser strictness rejecting a structurally bad source row, not a product bug.
- Validation: backend 378/378 locally (370 existing + 5 preview + 3 router). Frontend tsc + build green. Full browser smoke test passed.
- 378 tests at ST2 close

**ST3 (dashboard with current overdue picture):**
- `GET /dashboard` endpoint: typed Pydantic response with total overdue (includes possibly_paid), overdue today (live due_date math, not stored days_overdue), disputed/possibly_paid as overdue subsets, 5-bucket aging (Current, 1–7, 8–30, 31–60, 60+), top exposure customer, recent changes feed (overfetch 50 → filter → trim 15), last import, stale-data indicator (>24h)
- Dashboard page replacing placeholder: wow-moment narrative strip, 4 summary cards, aging breakdown table, recent changes feed with per-action-type icons, last import footer, stale-data warning (default Alert + amber classes), empty state for no-import accounts
- shadcn v3 Table component added manually (not via shadcn@latest)
- Key invariants established: all overdue calculations use live date math (CURRENT_DATE - due_date), never stored days_overdue field. Total overdue includes possibly_paid (consistent with M3-ST2 doctrine). Payment Review card shows possibly_paid as flagged subset. Disputed/possibly_paid counts require due_date < today (true overdue subsets). Aging reconciliation: SUM(overdue buckets) == total_overdue_amount, Current bucket excluded. Amount serialization: fixed 2-decimal strings ("2500.00"). Activity feed filtered server-side for operator-relevant action_types only.
- Key corrections: pending-import banner removed (no clean resume path), aging aligned to product-definition §2.4, possibly_paid included in headline total, overdue_today corrected from first_overdue_at to live due_date math, disputed/possibly_paid scoped as overdue subsets.
- Validation: backend import OK, 20 dashboard tests passed, frontend tsc + build green.
- 398 tests at ST3 close

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
| 30 | Overdue spike threshold: delta ≥ 3 AND post-count ≥ 4 | Absolute delta catches spikes at any baseline. Floor of 4 prevents first-import noise. Suppressed for customers first created in current import (no prior baseline). | 2026-03-22 |
| 31 | Cluster risk threshold: ≥ 3 open overdue invoices, threshold-crossing only | Flags when pre < 3 AND post >= 3. Does NOT re-fire while above threshold. Only status='open' with due_date < today counts. New customers crossing from 0 → 3+ ARE flagged. | 2026-03-22 |
| 32 | Multiple anomalies per invoice allowed | Balance increase + due date change are independent signals. Each gets its own Activity record. A single invoice can produce 1–3 anomalies in one confirm pass. | 2026-03-22 |
| 33 | All anomalies are differential | Every anomaly type flags a transition detected during this specific import, not a standing condition. This prevents noise accumulation in the action queue and keeps anomalies actionable. | 2026-03-22 |
| 34 | Trust-calibrated automation doctrine | Constitution §5.9 strengthened from "AI is subordinate" to trust-calibrated automation: maximum trustworthy automation, deterministic where sufficient, AI where it compresses ambiguity, expose uncertainty, smallest pre-digested fallback. Repo-wide AI-role drift corrected: wedge (8 locations), architecture stack table, product-definition heading. Diff engine, anomaly flagging, and fuzzy matching are deterministic — not AI. | 2026-03-22 |
| 35 | Review gate vs audit gate in workflow | Normal reviews validate changed files and related files. Audit gates scan repo-wide for contradictions in shared terminology, AI/automation role claims, stale references, and invariant statements. Audit is mandatory at milestone close-outs, docs-consolidation passes, and post-completion doctrine writebacks. Discovered during M3 close-out when normal reviews missed 10+ stale contradictions in files outside edited sections. | 2026-03-22 |
| 36 | Registration is email+password only; company_name collected during onboarding | Lowest friction signup. company_name nullable on Account, set via PATCH /auth/account. European defaults (EUR, Europe/Paris) applied at account creation. | 2026-03-23 |
| 37 | Email normalized on register and login | `.strip().lower()` before lookup/storage. Prevents duplicate-case accounts and login confusion. | 2026-03-23 |
| 38 | Account isolation via auth-derived context in M4 | `current_user.account_id` validated on all account-scoped routes. Frontend uses GET /auth/me to derive account_id — never user-supplied in URLs. Basic tenant isolation in M4; broader auth hardening (verification, rate limiting, deeper trust) remains M8. | 2026-03-23 |
| 39 | Template saved via explicit endpoint, idempotent per import | `POST /imports/{id}/save-template` persists the mapping. Frontend calls it when user confirms mapping (before import confirm). If import already has template_id, repeated calls update rather than duplicate. Preserves mapping work even if import is later cancelled. | 2026-03-23 |
| 40 | Template auto-apply: exact header-set match, one-candidate rule | Normalized set of mapped source columns must exactly equal normalized file headers. Compatible delimiter/decimal_separator when both non-null. Exactly one template must match. Intentionally strict — loosened later with evidence if needed. | 2026-03-23 |
| 41 | bcrypt pinned to 4.1.3 for passlib compatibility | passlib 1.7.4 crashes against bcrypt 5.x on Python 3.14. Pin discovered during Codex verification. | 2026-03-23 |
| 42 | ST1 preview contract is parse/mapping only | create_pending_import() returns IngestionResult preview, duplicate warning, fuzzy matches. Does NOT return business diff (new/updated/disappeared/anomalies). Business diff preview endpoint deferred to M4-ST2. Frontend must present ST1 preview as mapping review, not business-change preview. | 2026-03-23 |
| 43 | Do not use shadcn@latest while repo is on Next.js 14 + Tailwind CSS 3 | shadcn@latest defaults to v4 which requires Tailwind 4. Discovered when Part 2 initial commit broke npm run build. Repair replaced v4 with manual shadcn v3. | 2026-03-24 |
| 44 | Frontend auth uses explicit auth mode, not token-presence inference | apiFetch(path, options, auth) with "required" or "none". Prevents stale-token trap where login/register 401s trigger false session-expired redirects. | 2026-03-24 |
| 45 | Mapping editor renders fixed target-field list, not just preview mappings | All 14 canonical fields shown with dropdowns, initialized from preview where matched. Prevents unmappable required fields when preview auto-detection misses them. | 2026-03-24 |
| 46 | Shared-planner architecture for preview/confirm parity | preview_import() and confirm_import() share prepare_import_context() + build_import_plan(). Planner operates on frozen dataclasses (ExistingInvoiceSnapshot, ExistingCustomerSnapshot), not ORM objects. _apply_import_plan() uses plan data only — never re-runs matching. Parity test mandatory. Replaced earlier rollback-based dry-run proposal after GPT review identified db.commit() inside confirm_import() as a blocker. | 2026-03-24 |
| 47 | Preview anomaly serialization uses explicit allowlist | _serialize_preview_anomaly() filters anomaly.details through PREVIEW_ANOMALY_SAFE_DETAIL_KEYS. Prevents placeholder customer IDs, internal invoice IDs, or other non-display-safe fields from leaking into the preview API response. | 2026-03-24 |
| 48 | errors renamed to skipped_rows across import domain | ImportRecord column, confirm response, preview response, import_committed Activity details all use skipped_rows. Semantic clarity: these are non-blocking row-level skips (missing fields, invalid dates, duplicates), not blocking errors. Blocking failures raise ValueError and return 400/404. | 2026-03-24 |
| 49 | Trust screen uses No longer in file wording for disappeared invoices | Neutral label. Does not imply paid, credited, or any other disposition. Per-disappeared-invoice disposition UX is explicitly deferred. | 2026-03-24 |
| 50 | Cancel on trust screen means local navigation abandonment only | No backend discard/cleanup endpoint. Pending ImportRecord stays in pending_preview state. Orphaned pending imports are acceptable for v1. Lifecycle hygiene deferred. | 2026-03-24 |
| 51 | Dashboard uses live date math, not stored days_overdue | Invoice.days_overdue is only updated during import commits and becomes stale between imports. Dashboard computes all overdue/aging from (CURRENT_DATE - due_date) in SQL. This pattern must be followed by any future feature that reads overdue status. | 2026-03-24 |
| 52 | Total overdue includes possibly_paid; subset cards require due_date < today | possibly_paid remains outstanding until user-confirmed payment (M3-ST2 doctrine). Dashboard headline includes it. Payment Review card shows the subset. Both disputed_count and possibly_paid_count require due_date < today to be true overdue subsets. | 2026-03-24 |
| 53 | Dashboard amount serialization: fixed 2-decimal strings | All Decimal money fields in the dashboard API response are serialized as fixed 2-decimal strings (e.g., "2500.00", "0.00") via Decimal.quantize(). Prevents floating-point drift and establishes a pinned API contract for frontend consumers. | 2026-03-24 |
| 54 | Recent changes feed: overfetch → filter → trim | Dashboard fetches 50 activity candidates from DB, filters in Python (drops invoice_updated without meaningful change keys), returns first 15 retained. Prevents LIMIT-then-filter starvation. Meaningful change keys: outstanding_amount, due_date, status. | 2026-03-24 |
| 55 | Dockerfile ARG for NEXT_PUBLIC_API_URL | Next.js inlines NEXT_PUBLIC_* at build time. Docker build stage has no access to Railway service env vars unless declared via ARG. Added ARG + ENV before `npm run build` in frontend/Dockerfile. | 2026-03-25 |

## Queued Items

| Item | Target Milestone | Notes |
|------|-----------------|-------|
| Update `company_id` comment from "IČO in Czech" to generic "company registration number" | Next schema pass | Cosmetic but signals correct mental model |
| Add Italian to required reminder template languages | M5 (Action Execution) | FR/IT are primary markets; Italian must be first-class |
| Rotate Railway PostgreSQL password | ASAP | Public URL with credentials used in terminal session during migration |
| File storage: replace local disk with object storage + encryption | Post-M3 | ST1 uses plain `UPLOAD_DIR` on local disk. Railway filesystem is ephemeral. Acceptable for dev, not production. |
| Optimize DB test runtime (~15min is slow) | Post-M3 | Per-test NullPool engine is correctness-first. Revisit faster isolation (e.g. pytest-asyncio loop scope config) when milestone pressure is lower. |
| Recompute Customer.last_invoice_date alongside aggregate recalculation | Post-M3 | ST2 recalculates total_outstanding and invoice_count but not last_invoice_date. After disappearance or reassignment, last_invoice_date on the old customer could reference an invoice no longer active there. Low severity for v1. |
| Tighten ambiguous-duplicate handling from warn-and-skip to fail-fast | Post data-repair tooling | Decision #21. Revisit when users have manual invoice merge/delete tooling. |
| Python 3.14 dependency warnings (OpenAI/Pydantic V1 internals, Starlette async) | Maintenance | Non-blocking. Observed during ST2 local validation. |
| Customer relationship/group intelligence | Post-M3 (likely M6+) | Separate from identity resolution. Likely requires CustomerGroup model with explicit membership, suggested-link workflow, and distinct UI. Not an extension of merge_history or fuzzy matching. See decision #23. |
| Multi-candidate fuzzy matching for user confirmation | Post-M3 | Current ST3 returns single best candidate per file customer. Future: return top N for richer confirmation UX. |
| docs/opportunities.md maintenance | Ongoing | Strategic/commercial opportunities discovered during build. Update when major product insights emerge. See docs/opportunities.md. |
| docs/ai-engineering-workflow.md maintenance | Ongoing | Update when workflow learnings emerge during build. |
| Import quality intelligence (CSV/XLSX paths) | M4–M7 | Detect shaky imports: abnormal skip rates, duplicate rates, low-confidence mapping. Surface exact problematic rows. See opportunities.md. |
| Low-confidence extraction / document rescue flow | Post-v1 (v1.2+) | Contingent on expanding v1 input boundary beyond CSV/XLSX. See opportunities.md. |
| Future anomaly families | M4–M7 | Import-quality, data-integrity, identity, history/oscillation anomalies. See opportunities.md. |
| Run Alembic migration on Railway production DB | ASAP | `a1b2c3d4e5f6` (nullable company_name, EUR/Paris defaults). Railway auto-deploys code but does NOT auto-run migrations. |
| Pending import lifecycle hygiene (orphan cleanup) | Post-M4 | Cancel leaves ImportRecord in pending_preview. No cleanup endpoint yet. Acceptable for v1 single-user accounts. |
| Humanized anomaly type labels in trust screen | M4 polish or M5 | Trust screen currently shows raw anomaly_type strings (cluster_risk, balance_increase). Future: human-readable labels. |
| Scope label polish on trust screen | M4 polish or M5 | Footer can show Scope: Unknown. Future: contextual label or omit when unknown. |
| Run Alembic migration 8a7266974e1b on Railway production DB | ASAP | errors -> skipped_rows rename. Railway does not auto-run migrations. |
| Webhook signature verification | M4 (dedicated sub-task) | RESEND_WEBHOOK_SECRET exists but is not used. HIGH severity. Explicitly deferred from ST1. |

## Infrastructure

| Service | Status | Notes |
|---------|--------|-------|
| GitHub | ✅ | https://github.com/panda4505/overdue-cash-control |
| Railway backend | ✅ | https://overdue-cash-control-production.up.railway.app |
| Railway frontend | ✅ | https://noble-possibility-production.up.railway.app |
| Frontend Docker env | ✅ | ARG NEXT_PUBLIC_API_URL injected at build stage so Next.js inlines it during `npm run build` |
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
