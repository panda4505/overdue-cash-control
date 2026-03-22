# BUILD LOG — Overdue Cash Control

> **Purpose:** Paste this entire file at the start of every AI session
> (Claude, Codex, or any other). It is the single source of truth for
> what exists, what works, what's broken, and what's next.

---

## Identity

- **Product:** Overdue Cash Control — collections workflow for EU SMBs
- **Builder:** Lorenzo (founder, tester, decision-maker)
- **AI engineer:** Codex in VS Code (code writing) + Claude (architecture, planning, reviews)
- **Stack:** Python/FastAPI backend, Next.js frontend, PostgreSQL on Railway, OpenAI + DeepSeek LLM, Resend email
- **Repo:** https://github.com/panda4505/overdue-cash-control

---

## Current State

- **Milestone:** 3 of 10 — IN PROGRESS
- **Sub-task:** M3-ST1 COMPLETE, M3-ST2 next
- **Status:** M3-ST1 (first import commit path) is done. 221 tests green. Users can upload a file to an account-scoped endpoint, receive a preview (even with imperfect mapping), then confirm to commit Customers, Invoices, ImportRecord, and Activity to PostgreSQL. Normalization (EU legal suffix stripping), mapping validation, duplicate hash detection, change_set for rollback, and audit fields all implemented. Existing stateless `POST /upload` preview is untouched.
- **Blockers:** None
- **Last session:** 2026-03-22

---

## What Exists (file inventory)

```
backend/
  app/main.py           — FastAPI app, /, /health, /test-email, CORS, webhook + upload + imports router registration. CHANGED in session 10: added imports_router and confirm_router.
  app/config.py         — env var loading for DB, LLM, Resend, auth, frontend, UPLOAD_DIR, TEST_DATABASE_URL. CHANGED in session 10: added UPLOAD_DIR and TEST_DATABASE_URL settings.
  app/database.py       — async SQLAlchemy engine + session
  app/services/llm_client.py — OpenAI primary, DeepSeek fallback
  app/services/file_parser.py — CSV/XLSX parser with encoding detection, delimiter detection, header row detection, format-shaped numeric/date type inference. 4 number patterns, European-first encoding fallback with mojibake rejection guard, pure-integer ID protection. CHANGED in session 9: added suspicious-character guard in _detect_encoding() to reject mojibaked single-byte decodes.
  app/services/column_mapper.py — Column mapper with 6-language deterministic dictionary (FR/IT/EN/CZ/DE/ES), template validation with normalized comparison + always-enrich, async LLM fallback with hallucination protection. 14 canonical fields (12 core, 2 auxiliary). 48 tests.
  app/services/ingestion.py — Shared canonical ingestion pipeline: parse → map → package preview. SHA-256 file hash. JSON-serializable sample rows with original headers. to_dict() for shared serialization. CHANGED in session 9: added to_dict() method.
  app/services/normalization.py — Invoice number and customer name normalization for matching. EU legal suffix stripping (CZ/DE/FR/IT/ES/EN). normalize_invoice_number() strips separators, lowercases. normalize_customer_name() strips legal suffixes (s.r.o., GmbH, SAS, S.r.l., etc.), NFC-normalizes, lowercases. NEW in session 10.
  app/services/import_commit.py — Import commit service: create_pending_import() (parse + save file + ImportRecord), confirm_import() (re-parse + validate mapping + create Customers/Invoices + Activity + change_set). Gates pending import on parse success not mapping success. Row validation before customer creation (no orphan customers). Repo-aligned change_set keys. Audit fields (errors, warnings_text). NEW in session 10.
  app/models/__init__.py  — imports all 7 models for Alembic
  app/models/account.py   — Account (company using the product)
  app/models/user.py      — User (person logging in, separate for future multi-user)
  app/models/customer.py  — Customer (debtor, with fuzzy match fields + merge_history JSONB)
  app/models/invoice.py   — Invoice (core record, 8 statuses, recovery tracking, data lineage, 4 composite indexes)
  app/models/import_record.py — ImportRecord (full audit trail, change_set JSONB for rollback, cost tracking)
  app/models/import_template.py — ImportTemplate (saved column mappings, format hints: decimal_separator + thousands_separator, usage counter). CHANGED in session 6: replaced number_format with explicit separator fields, updated comments to multilingual examples.
  app/models/activity.py  — Activity (timeline of all events, flexible JSONB details, 4 indexes)
  app/routers/upload.py     — POST /upload endpoint: thin wrapper over ingestion service, uses result.to_dict(). CHANGED in session 9: replaced _serialize_ingestion_result with result.to_dict().
  app/routers/imports.py   — Import lifecycle endpoints: POST /accounts/{account_id}/imports/upload (account-scoped pending import + preview), POST /imports/{import_id}/confirm (commit to DB). Explicit account 404, file validation, ValueError→HTTP status mapping. NEW in session 10.
  app/routers/webhooks.py — Resend inbound webhook: downloads attachments, filters by supported extension, calls ingest_file() for each, returns ingestion results. Skips unsupported files and missing download URLs with reason. CHANGED in session 9: wired to ingestion pipeline, added skip handling.
  app/routers/__init__.py — routers package marker
  app/utils/__init__.py — utils package placeholder
  app/__init__.py       — app package marker
  app/services/__init__.py — services package marker
  alembic/versions/4a129036b96f_create_all_tables.py — initial migration creating all 7 tables
  alembic/versions/7d3f8c2b1a90_replace_number_format_with_separator_fields.py — migration: drop number_format, add decimal_separator + thousands_separator on import_templates
  alembic/env.py        — updated to import all models for autogenerate
  alembic/script.py.mako — Alembic revision template
  alembic.ini           — Alembic config
  tests/__init__.py     — tests package placeholder
  tests/conftest.py        — Shared DB test fixtures: per-test engine with NullPool (root cause fix: asyncpg connections bound to session-scoped event loop fail on function-scoped test loops), truncate-based cleanup (TRUNCATE ... RESTART IDENTITY CASCADE), test_account factory, UPLOAD_DIR override, HTTPX test_client with get_db override. Requires TEST_DATABASE_URL distinct from DATABASE_URL (RuntimeError if missing or matching). NEW in session 10.
  tests/test_file_parser.py   — 86 tests: 5 CSV fixtures + 1 XLSX fixture + inline edge cases + 4 encoding fallback tests (Windows-1250, ISO-8859-1, ISO-8859-15, ISO-8859-2). CHANGED in session 9: added TestGermanXLSX (8 tests) and TestEncodingFallback (4 tests).
  tests/test_column_mapper.py — 48 tests (unchanged).
  tests/test_ingestion.py   — Service-level ingestion tests: all 6 fixtures, hash, serialization, template pass-through, error handling, XLSX ingestion. CHANGED in session 9: added XLSX test, renamed smoke test to cover 6 fixtures.
  tests/test_upload.py      — HTTP endpoint tests: upload success (CSV + XLSX), file validation, response shape, hash verification. CHANGED in session 9: added XLSX upload test.
  tests/test_webhooks.py    — 10 tests: 3 parity tests (upload vs email produce identical results across all 5 CSV fixtures), 7 webhook endpoint tests (success, skip PDF, no attachments, non-email event, download failure, missing download URL, mixed multi-attachment). NEW in session 9.
  tests/test_normalization.py — 19 tests (6 invoice number + 13 customer name): parametrized normalization tests for EU legal suffixes (CZ/DE/FR/IT/ES/EN), compound suffixes, unicode, whitespace, empty strings. NEW in session 10.
  tests/test_import_commit.py — 25 tests: 5 pending import tests (success, imperfect mapping, duplicate hash, file saved, parse failure), 15 confirm tests (invoices, customers, dedup, status, audit fields, activity, timestamps, days_overdue, change_set structure, double-confirm, nonexistent, customer reuse, normalized numbers, orphan guard, all-fixtures smoke), 5 mapping validation tests (invalid source, missing required, amount fallback, no amount, duplicate source). DB-backed via conftest.py. NEW in session 10.
  tests/test_imports_router.py — 8 tests: upload preview+import_id, confirm summary, unsupported type 400, empty file 400, nonexistent account 404, nonexistent import 404, already confirmed 409, invalid mapping 400. DB-backed via conftest.py. NEW in session 10.
  Dockerfile            — Python 3.12-slim backend image for Railway (production). Local dev/test runs Python 3.14.3.
  railway.toml          — Railway deploy config
  requirements.txt      — all backend deps. CHANGED in session 10: added pytest-asyncio==1.3.0.
frontend/
  src/app/page.tsx      — landing page for Overdue Cash Control
  src/app/layout.tsx    — root layout for the Next.js app
  src/app/globals.css   — global Tailwind styles
  src/app/fonts/        — bundled Geist font files
  Dockerfile            — Next.js container image for Railway
  package.json          — frontend scripts and dependencies
  package-lock.json     — locked npm dependency tree
  next.config.mjs       — Next.js config
  postcss.config.mjs    — PostCSS config
  tailwind.config.ts    — Tailwind config
  tsconfig.json         — TypeScript config
docs/
  architecture.md       — full stack and design decisions
  constitution.md       — governing principles, decision filter, beachhead definition, pricing, exclusions
  product-definition.md — screen-by-screen UX, data model (aligned with actual build), engine specs, deferred entities marked
  trajectory.md         — 10 milestones from architecture to launch, aligned with actual build (M1 marked complete, Codex/Claude dual model, Resend, OpenAI/DeepSeek)
  wedge-v1.md           — canonical wedge statement, scope boundary, input layer, AI role, aligned with actual build (Resend, preview-before-commit, no PDF parsing in v1)
sample-data/
  pohoda_ar_export.csv   — semicolon-delimited, Czech headers, DD.MM.YYYY dates, 15 invoices
  fakturoid_ar_export.csv — comma-delimited, English headers, ISO dates, EUR, 15 invoices
  messy_generic_export.csv — Czech headers, messy data, missing fields, Czech number formatting, 12 invoices
  french_ar_export.csv    — semicolon, French headers, DD/MM/YYYY, space+comma numbers, Windows-1252 encoding, SARL/SAS/SA/EURL/SCI suffixes
  italian_ar_export.csv   — semicolon, Italian headers, DD/MM/YYYY, dot+comma numbers (45.000,00), S.r.l./S.p.A./S.a.s./S.n.c. suffixes
  german_ar_export.xlsx     — XLSX, German headers, DD.MM.YYYY dates, dot+comma numbers (45.000,00), 10 invoices, 2 sheets (Rechnungen + Zusammenfassung). NEW in session 9.
  create_xlsx_fixture.py    — One-time script to regenerate german_ar_export.xlsx via openpyxl. NEW in session 9.
  README.md              — documents all edge cases, format coverage matrix, and European scope. CHANGED in session 6: full rewrite.
BUILD_LOG.md            — this file
README.md               — project overview
.gitignore              — Python + Node + env files
```

---

## Session History

### Session 10 — 2026-03-22
- **M3-ST1: First import commit path**
  - Created `backend/app/services/normalization.py`: `normalize_invoice_number()` (strip separators, lowercase) and `normalize_customer_name()` (strip EU legal suffixes for CZ/SK/DE/FR/IT/ES/EN, NFC normalize, lowercase). 19 parametrized tests in `test_normalization.py`.
  - Created `backend/app/services/import_commit.py`: two-phase import lifecycle:
    - `create_pending_import()`: calls `ingest_file()`, gates on parse success (not mapping success — users can fix mapping before confirming), checks duplicate SHA-256 hash, saves file to disk (`UPLOAD_DIR/{account_id}/{import_id}/filename`), creates `ImportRecord(status=pending_preview)`, explicit `await db.commit()` with file cleanup on failure.
    - `confirm_import()`: validates confirmed mapping (source columns exist, required targets present, no duplicate source assignments), re-parses stored file, validates ALL row-level fields before customer creation (no orphan customers), creates Customer (exact normalized name match within account, with contact enrichment on reuse), creates Invoice (with `days_overdue`, `first_overdue_at`, `normalized_invoice_number`), builds `change_set` with repo-aligned keys (`created`, `updated`, `disappeared`, `customers_created`, `customers_merged`), populates `ImportRecord.errors` and `warnings_text`, creates `Activity(action_type=import_committed)`, updates `Account.first_import_at`/`last_import_at`.
  - Created `backend/app/routers/imports.py`: `POST /accounts/{account_id}/imports/upload` (account-scoped, explicit 404 on missing account) and `POST /imports/{import_id}/confirm` (ValueError→404/409/400 mapping).
  - Modified `backend/app/main.py`: registered `imports_router` and `confirm_router`.
  - Modified `backend/app/config.py`: added `UPLOAD_DIR` and `TEST_DATABASE_URL` settings.
  - Modified `backend/requirements.txt`: added `pytest-asyncio==1.3.0`.
  - Created `backend/tests/conftest.py`: DB test fixtures with per-test engine using `NullPool` (no connection pooling) to avoid asyncpg cross-event-loop errors. Truncate-based cleanup (`TRUNCATE ... RESTART IDENTITY CASCADE`) after each test. `test_account` factory, `_override_upload_dir` autouse fixture, `test_client` with `get_db` override. Requires `TEST_DATABASE_URL` — `RuntimeError` if missing or matches `DATABASE_URL`.
  - Created `backend/tests/test_import_commit.py`: 25 service-level DB tests covering pending import creation, imperfect mapping acceptance, duplicate warning, file persistence, confirm lifecycle (invoices, customers, dedup, audit fields, activity, timestamps, days_overdue, change_set structure, double-confirm rejection, orphan customer guard), mapping validation, and all-fixtures smoke test.
  - Created `backend/tests/test_imports_router.py`: 8 endpoint tests covering upload preview, confirm summary, error codes (400/404/409).
  - Existing `POST /upload` endpoint and all 188 existing tests untouched — zero regressions.
  - **Test fixture debugging**: Initial conftest used session-scoped `db_engine` with savepoint-based isolation (`begin_nested()`, `join_transaction_mode="create_savepoint"`, `after_transaction_end` event listener). This failed on Python 3.14 + asyncpg + pytest-asyncio because the session-scoped engine created connections on one event loop while function-scoped tests ran on another (`RuntimeError: Task ... got Future ... attached to a different loop`). All "cannot perform operation: another operation is in progress" errors were downstream symptoms. Root cause fix: eliminated session-scoped engine, switched to per-test `create_async_engine(NullPool)` + truncate cleanup. 4 prompt iterations to diagnose and fix.
  - 221 tests passing (86 parser + 48 mapper + 15 ingestion + 10 upload + 10 webhooks + 19 normalization + 25 import commit + 8 imports router)
  - Committed as `78e6f25`. DB tests require `TEST_DATABASE_URL` (dedicated test database, must differ from `DATABASE_URL`).
- **Next:** M3-ST2 (diff engine — second import to the same account identifies new, updated, unchanged, and disappeared invoices)

### Session 9 — 2026-03-21
- **M2-ST4: Email webhook wiring + parity tests**
  - Added `to_dict()` to `IngestionResult` in `backend/app/services/ingestion.py` for shared serialization
  - Simplified `backend/app/routers/upload.py`: deleted `_serialize_ingestion_result`, now uses `result.to_dict()`
  - Wired `backend/app/routers/webhooks.py` to call `ingest_file()` for each supported attachment (csv/tsv/xlsx), skip unsupported types and download failures with reason, return ingestion results in response
  - Hardened webhooks.py: added else clause for missing `download_url` (attachments without a URL now land in `attachments_skipped` instead of silently falling through)
  - Created `backend/tests/test_webhooks.py`: 3 parity tests (same bytes produce identical results via upload vs email across all 5 CSV fixtures) + 7 webhook endpoint tests with mocked Resend API
  - All reviewed by GPT-5.4 before and after implementation; 2 mock-shape fixes applied (`.text` attribute on mock response, non-empty `data.attachments` in webhook payload)
  - 155 tests passing after ST4
- **M2-ST5: XLSX fixture + encoding fallback proof**
  - Created `sample-data/german_ar_export.xlsx` via `sample-data/create_xlsx_fixture.py`: 10 German invoices (GmbH/AG/e.K. suffixes, umlauts), 2 sheets (Rechnungen + Zusammenfassung), dot-comma numbers, DD.MM.YYYY dates, all values as strings
  - Added `TestGermanXLSX` (8 tests) in `test_file_parser.py`: sheet selection, German headers, date/numeric detection, dot-comma conversion, zero balance
  - Added `TestEncodingFallback` (4 inline tests) in `test_file_parser.py`: Windows-1250 Czech, ISO-8859-1 German, ISO-8859-15 French (€ symbol), ISO-8859-2 Czech — all outcome-focused (no exact encoding label assertions)
  - Encoding tests exposed a real parser bug: `_detect_encoding()` in `file_parser.py` accepted the first single-byte codec that didn't throw `UnicodeDecodeError`, even when it produced mojibake (e.g. Č→È, €→¤). Fixed with a +9 line guard that rejects decoded text containing C1 control characters (127–159) or known mojibake markers (¤©¹»¾)
  - Added XLSX ingestion test in `test_ingestion.py`, XLSX upload test in `test_upload.py`
  - Renamed `test_all_five_fixtures_ingest_successfully` → `test_all_fixtures_ingest_successfully` (now covers 6 fixtures)
  - 169 tests passing after ST5
- **Milestone 2 closed.** All repo-level exit gates passed. Real customer export validation deferred to pilot (M9).
- **Next:** Update BUILD_LOG.md and trajectory.md to reflect M2 closure, then begin Milestone 3 (Reconciliation & AI Layer).

### Session 8 — 2026-03-21
- Created `backend/app/services/ingestion.py`: shared canonical ingestion pipeline (parse → map → package preview result) used by both upload and email paths
- SHA-256 file hash computed on every ingestion for future duplicate detection
- Sample rows (first 10) extracted with original headers and JSON-serializable values
- Created `POST /upload` endpoint in `backend/app/routers/upload.py`: thin wrapper over ingestion service, validates file extension and emptiness, returns full preview JSON
- Registered upload router in `backend/app/main.py`
- No database writes, no file persistence, no auth — those are separate concerns with separate implementation steps
- Service tests + endpoint tests passing across all 5 fixtures
- **Next:** Wire email webhook to call the same ingestion service. Add parity test proving upload and email produce identical results for the same file.

### Session 7 — 2026-03-21
- Built the column mapper service: async mapper with three matching strategies — saved template validation, deterministic dictionary, and LLM fallback
- 6-language deterministic dictionary (FR/IT/EN/CZ/DE/ES) with ~150 aliases across 14 canonical fields. All 5 fixtures map fully without LLM.
- Template path: validates `{target_field: source_column}` mapping against normalized headers, rejects duplicate source assignments, always enriches optional fields via deterministic matching after template application
- Deterministic matching: exact (1.0) → synonym (0.9) → partial (0.7, restricted to headers with ≥3 tokens and ≥60% bidirectional overlap). Dangerous standalone aliases removed (company, balance, remaining, mail, correo, contact, reference)
- LLM fallback: triggers when required fields unmapped or confidence < 0.6. Validates response — rejects hallucinated source columns and unknown target fields, clamps confidence, deduplicates. LLM cannot override deterministic matches ≥ 0.7
- Conflict resolution: one source → one target, one target → one source, conflicts recorded with winner/loser/confidence. Type-compatible candidate preferred over incompatible at equal confidence
- Amount fallback: when only gross_amount is mapped, `amount_fallback_active=True` signals downstream. gross_amount confidence used as stand-in in required-field average
- 14 canonical fields split into core (12, stored in DB) and auxiliary (2: status, contact_name — preview-only)
- Surgical fix applied after initial implementation: changed `success` from hardcoded True to `bool(mappings)`, narrowed `_is_hard_mismatch()` to only numeric→date and string→numeric, added 7 targeted tests for untested code paths
- Mapper design and surgical fix were reviewed before implementation to catch dictionary, template, and type-mismatch risks early
- Final state: 48 tests passing (41 original + 7 from surgical fix)
- **Next:** Build manual upload endpoint (`POST /upload`) and wire email webhook to feed attachments through the parser→mapper pipeline. Both paths must produce identical results for the same file.

### Session 6 — 2026-03-21
- Built `backend/app/services/file_parser.py`: CSV/XLSX parser with encoding detection (chardet + Western European priority fallback), delimiter detection (Sniffer + consistency scoring), header row detection (scoring heuristic), and format-shaped numeric/date type inference
- Four number separator patterns supported: space+comma, dot+comma, comma+dot, plain dot decimal — no country labels in code
- Pure integer columns (SIRET, IČO, Partita IVA) protected from numeric misclassification — require decimal punctuation evidence
- Slash dates always DD/MM (European convention), no MM/DD disambiguation
- .xls rejected with clear re-export message (openpyxl limitation)
- Created `sample-data/french_ar_export.csv` (Windows-1252, semicolon, French headers, space+comma numbers, DD/MM/YYYY, 12 rows)
- Created `sample-data/italian_ar_export.csv` (UTF-8, semicolon, Italian headers, dot+comma numbers, DD/MM/YYYY, 12 rows)
- Rewrote `sample-data/README.md` with full format coverage matrix
- Replaced `number_format` field on ImportTemplate with `decimal_separator` + `thousands_separator` (model + manual Alembic migration `7d3f8c2b1a90_replace_number_format_with_separator_fields.py`)
- Migration applied successfully to production Railway PostgreSQL (Alembic upgrade 4a129036b96f → 7d3f8c2b1a90)
- 74 parser tests passing across 5 CSV fixtures + 3 inline edge case classes. XLSX parsing implemented but not yet validated with a real XLSX fixture.
- Parser scope and migration plan were reviewed before implementation to catch schema and parser-design risks early
- Established European-first invariant: France and Italy are primary launch markets, Czech is supported but not default reference
- **Next:** Build the column mapper (deterministic dictionary for FR/IT/CZ/EN/DE/ES headers → saved template matching → LLM fallback). Also: create an XLSX test fixture to validate XLSX parsing path.

### Session 5 — 2026-03-21
- Cross-document consistency review with Claude (architecture, planning). GPT-5.4 used as second reviewer.
- Fixed 20+ inconsistencies across all 6 docs: milestone count (10 not 12), auth milestone references, deferred entity milestone numbers, Import Preview missing from trajectory M4 build order, email provider history note, pilot invoice threshold raised to 50+, constitution companion docs completed, sample-data label corrected, data flow milestone label removed, upload-first engineering vs UX clarification added, build log git instruction clarified
- Codex caught 2 additional stale "12 milestones" references during grep verification
- No code changes. Docs only.
- **Next:** Build the file parsing engine (CSV/XLSX with encoding detection, delimiter detection, header row detection) — first sub-task of Milestone 2

### Session 4 — 2026-03-20
- Designed and created 7 SQLAlchemy models: Account, User, Customer, Invoice, ImportRecord, ImportTemplate, Activity
- Key design decisions: separated User from Account for future multi-user; added soft deletes on Customer and Invoice; added data lineage fields (first_seen_import_id, last_updated_import_id); added recovery tracking (recovery_confirmed_at, recovery_import_id); added cost/performance tracking on ImportRecord (parse_duration_ms, mapping_method, llm_tokens_used); added activation signals on Account (first_import_at, last_import_at, total_recovered_amount); added merge_history JSONB on Customer for auditable fuzzy matching
- Set up local Python venv, installed dependencies, upgraded SQLAlchemy from 2.0.36 to 2.0.48 (Python 3.14 compatibility fix)
- Generated Alembic migration and applied it to production Railway PostgreSQL — all 7 tables and indexes created
- Updated requirements.txt to pin sqlalchemy==2.0.48
- Caught stale `.env.example` still referencing Postmark — updated to Resend variables
- Updated exit gate section: marked M1 complete, added M2 exit gate criteria from trajectory
- Added OPENAI_API_KEY and DEEPSEEK_API_KEY to Railway backend environment variables — all M1 infrastructure accounts now complete
- **Next:** Build the file parsing engine (CSV/XLSX with encoding detection, delimiter detection, header row detection) and the deterministic column mapper

### Session 3 — 2026-03-20
- Added architecture decision doc to `docs/architecture.md` (stack, project structure, Railway architecture, LLM design, email architecture, data flow, security model, design principles)
- Created 3 synthetic AR export test files in `sample-data/`: `pohoda_ar_export.csv` (Czech/semicolon), `fakturoid_ar_export.csv` (English/comma/EUR), `messy_generic_export.csv` (messy Czech data with missing fields and inconsistent formatting)
- Added `sample-data/README.md` documenting all edge cases the ingestion engine must handle
- Removed `sample-data/*.csv` from `.gitignore` so synthetic test files can be committed
- Corrected build log: Current State blockers and sub-task, exit gate checkboxes, Accounts & URLs
- **Milestone 1 is now COMPLETE — all 8 exit gates passed**
- **Next:** Begin Milestone 2 — Ingestion Engine (upload-first). First task: define database models for Invoice, Customer, ImportRecord, ImportTemplate, Activity.

### Session 2 — 2026-03-20
- Switched email provider settings from Postmark to Resend in `backend/app/config.py`
- Added `GET /test-email` in `backend/app/main.py` to send outbound mail through `https://api.resend.com/emails`
- Added `POST /webhooks/resend/inbound` in `backend/app/routers/webhooks.py` and mounted the router in `backend/app/main.py`
- Implemented attachment lookup via `GET /emails/receiving/{email_id}/attachments` and download logging in `backend/app/routers/webhooks.py`
- Fixed an incorrect Resend attachments API path during live debugging and added `print(...)` logging for Railway visibility
- No automated tests were added this session; validation was manual through live outbound/webhook debugging
- **Next:** Verify Resend webhook signatures, persist/parse downloaded attachments, and remove or secure the public `/test-email` endpoint

### Session 1 — 2026-03-19
- Created GitHub repo and pushed Milestone 1 commits
- Generated backend scaffold in `backend/` (`app/main.py`, `app/config.py`, `app/database.py`, `app/services/llm_client.py`, Alembic config)
- Deployed the FastAPI backend to Railway and attached Railway PostgreSQL
- Verified `GET /health` returns `{"status":"ok","db":"connected","version":"0.1.0"}`
- Created the Next.js frontend in `frontend/src/app/page.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`, `frontend/package.json`, and `frontend/Dockerfile`
- Deployed the frontend live and confirmed the page loads
- Updated `BUILD_LOG.md` to reflect the live backend/frontend state
- **Next:** Set up Postmark account, build inbound email webhook, test outbound sending

---

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

---

## Open Bugs

- `backend/app/routers/webhooks.py` — `RESEND_WEBHOOK_SECRET` exists in config but the inbound webhook does not verify webhook signatures yet. Repro: `POST /webhooks/resend/inbound` with `{"type":"email.received","data":{...}}`. Severity: High.
- `backend/app/main.py` — `GET /test-email` is publicly reachable on the live backend and hardcodes `lorenzo.massimo.pandolfo@gmail.com` as the recipient. Repro: call `/test-email`. Severity: Medium.
- `backend/app/routers/webhooks.py` — inbound attachment bytes are processed through the ingestion pipeline but not persisted to disk or object storage. The bytes exist only for the duration of the HTTP request. If the webhook call fails or the server restarts mid-processing, the attachment is lost. Repro: send an inbound email; bytes are ingested but not saved. Severity: Medium. Mitigation: email can be re-sent.

---

## Accounts & URLs

| Service | Status | URL / Notes |
|---------|--------|-------------|
| GitHub repo | ✅ Created | https://github.com/panda4505/overdue-cash-control |
| Railway project | ✅ Created | Backend + frontend services are live |
| Railway PostgreSQL | ✅ Connected | Attached to backend; `/health` reports `db=connected` |
| Backend deploy | ✅ Live | https://overdue-cash-control-production.up.railway.app |
| Frontend deploy | ✅ Live | https://noble-possibility-production.up.railway.app |
| OpenAI API key | ✅ Added | Configured in Railway backend variables |
| DeepSeek API key | ✅ Added | Configured in Railway backend variables |
| Resend account | ✅ Created | Domain overduecash.com verified, inbound receiving via tuaentoocl.resend.app |
| Product domain | ✅ Registered | overduecash.com on Cloudflare, DNS verified by Resend |

---

## Current Milestone Exit Gate

> **Milestone 1: COMPLETE** — all 8/8 exit gates passed on 2026-03-20.
>
> **Milestone 2: COMPLETE** — all repo-level exit gates passed on 2026-03-21. 169 tests.
> - [x] CSV files parse correctly (comma and semicolon delimited) — verified across 5 CSV fixtures
> - [x] XLSX files parse correctly — verified with german_ar_export.xlsx (10 rows, 2 sheets, German headers, dot-comma numbers)
> - [x] Encoding detection works for UTF-8 and Windows-1252 — verified by pohoda/fakturoid/messy/italian (UTF-8) and french (Windows-1252) fixtures
> - [x] Encoding detection works for Windows-1250, ISO-8859-1, ISO-8859-15, ISO-8859-2 — verified by inline encoding fallback tests with mojibake rejection guard
> - [x] Column mapping works deterministically for known formats and falls back to LLM for unknown ones — verified across 6 fixtures spanning CZ/EN/FR/IT/DE, LLM path tested with mocked provider, 48 tests
> - [x] At least 5 export formats parse correctly — 6 synthetic fixtures (5 CSV + 1 XLSX) across 5 languages. Real customer export validation deferred to pilot (M9).
> - [x] Email ingestion wrapper feeds attachments into the same pipeline as manual upload — webhooks.py calls ingest_file() for each supported attachment
> - [x] Manual upload endpoint accepts CSV/XLSX and returns parsed results — POST /upload returns full parse + mapping preview
> - [x] Both ingestion paths produce identical results for the same file — parity tests across all 5 CSV fixtures confirm method is the only difference. XLSX proven end-to-end via upload; webhook parity for XLSX not yet tested separately.
>
> **Milestone 3 is done when:**
> - [ ] A second import to the same account correctly identifies new, updated, unchanged, and disappeared invoices
> - [ ] Fuzzy customer matching merges obvious name variants and asks for confirmation on ambiguous ones
> - [ ] Anomalies are flagged (balance increase, due date change, reappeared invoice, cluster risk)
> - [ ] No data lost or duplicated across sequential imports
>
> **M3-ST1 (first import commit path): COMPLETE** — 221 tests green on 2026-03-22. Pending import + confirm + Customer/Invoice creation + normalization + mapping validation + change_set + activity logging + duplicate detection + audit fields + no orphan customers.

---

## Queued Items (non-blocking)

| Item | Target Milestone | Notes |
|------|-----------------|-------|
| Change Account defaults: currency CZK → EUR, timezone Europe/Prague → Europe/Paris | M4 (Core UI) | Onboarding should detect locale and suggest defaults |
| Update `company_id` comment from "IČO in Czech" to generic "company registration number" | Next schema pass | Cosmetic but signals correct mental model |
| Add Italian to required reminder template languages | M5 (Action Execution) | FR/IT are primary markets; Italian must be first-class |
| Rotate Railway PostgreSQL password | ASAP | Public URL with credentials used in terminal session during migration |
| File storage: replace local disk with object storage + encryption | Post-M3 | ST1 uses plain `UPLOAD_DIR` on local disk. Railway filesystem is ephemeral. Acceptable for dev, not production. |
| ImportTemplate persistence: save confirmed mappings for reuse | M3 or M4 | Currently mapping round-trips through client. Saving as template is a separate feature. |
| Optimize DB test runtime (~15min is slow) | Post-M3 | Per-test NullPool engine is correctness-first. Revisit faster isolation (e.g. pytest-asyncio loop scope config) when milestone pressure is lower. |

---

## Reference Docs

The full product spec lives in these docs (paste relevant sections when needed, not every session):
- **Product constitution** (`docs/constitution.md`) — governing principles, decision filter, beachhead definition, pricing, exclusions
- **Wedge definition v1** (`docs/wedge-v1.md`) — canonical wedge statement, scope boundary, input layer, AI role. Aligned with actual build.
- **Product definition** (`docs/product-definition.md`) — screen-by-screen UX, data model, ingestion/reconciliation/escalation engine specs. Aligned with actual build as of M2 start.
- **Build trajectory** (`docs/trajectory.md`) — 10 milestones, session plans, exit gates, risk register. Aligned with actual build as of M2 start.
- **Buyer analysis** — harsh buyer assessment with pricing signals, shared during M1 close-out

---

## For the AI: How to Read This Log

1. Read **Current State** to know where we are
2. Read **What Exists** to know what files are in the repo
3. Read **Session History** (last 2-3 entries) to know recent context
4. Read **Open Bugs** before writing new code
5. Check **Decisions Made** before proposing architecture changes
6. When the session ends, Lorenzo will ask you to update this file — follow the instructions below
7. When Claude generates a Codex prompt, always include `git add . && git commit -m "..." && git push origin main` at the end if files were changed. Codex handles git directly (Lorenzo approves before execution in agent mode).

---

## For the AI: How to Update This Log at End of Session

When Lorenzo says "update the build log" or "wrap up the session", do this:

### 1. Current State
- Update milestone, sub-task, status, blockers, and date

### 2. What Exists (file inventory)
- Add any new files created this session with a short description
- Remove any files deleted
- Mark files that were significantly changed

### 3. Session History
- Add a new entry at the TOP of the session list (newest first):

```
### Session N — YYYY-MM-DD
- What was built/changed (be specific: file names, features, fixes)
- What was tested and the result
- What broke and whether it was fixed
- **Next:** the immediate next task for the following session
```

### 4. Decisions Made
- Add any new architecture or tool decisions to the table
- Include the rationale — future readers need to know WHY, not just WHAT

### 5. Open Bugs
- Add any new bugs: what happens, how to reproduce, severity
- Remove bugs that were fixed (move to the session history entry where they were fixed)

### 6. Accounts & URLs
- Update status of any accounts created or URLs that changed

### 7. Exit Gate
- Check off any completed items with [x]

### Rules
- **Be specific.** "Fixed parsing" is useless. "Fixed CSV parser choking on Windows-1250 encoded files from Pohoda — added chardet detection in parser.py" is useful.
- **File names matter.** Always reference exact file paths.
- **Never delete session history.** It's append-only.
- **Keep the log under 300 lines.** If it gets long, archive old sessions to `docs/session-archive.md` and keep only the last 5 sessions here.
- **Don't summarise — be concrete.** Someone reading this at 2 AM with no context should know exactly what state the project is in.
- **Always commit and push.** Every Codex prompt that modifies files should end with `git add . && git commit -m "descriptive message" && git push origin main`. Codex can do this directly — Lorenzo does not need to do it manually in the terminal.
