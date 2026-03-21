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

- **Milestone:** 2 of 10 — Ingestion Engine (upload-first)
- **Sub-task:** Email ingestion wrapper + parity tests
- **Status:** Shared ingestion service and manual upload endpoint complete. Parser → mapper pipeline exposed via POST /upload. Ready to wire email webhook to the same ingestion service.
- **Blockers:** None
- **Last session:** 2026-03-21

---

## What Exists (file inventory)

```
backend/
  app/main.py           — FastAPI app, /, /health, /test-email, CORS, webhook + upload router registration
  app/config.py         — env var loading for DB, LLM, Resend, auth, frontend
  app/database.py       — async SQLAlchemy engine + session
  app/services/llm_client.py — OpenAI primary, DeepSeek fallback
  app/services/file_parser.py — CSV/XLSX parser with encoding detection, delimiter detection, header row detection, format-shaped numeric/date type inference. 4 number patterns, European-first encoding fallback, pure-integer ID protection.
  app/services/column_mapper.py — Column mapper with 6-language deterministic dictionary (FR/IT/EN/CZ/DE/ES), template validation with normalized comparison + always-enrich, async LLM fallback with hallucination protection. 14 canonical fields (12 core, 2 auxiliary). 48 tests.
  app/services/ingestion.py — Shared canonical ingestion pipeline: parse → map → package preview. SHA-256 file hash. JSON-serializable sample rows with original headers.
  app/models/__init__.py  — imports all 7 models for Alembic
  app/models/account.py   — Account (company using the product)
  app/models/user.py      — User (person logging in, separate for future multi-user)
  app/models/customer.py  — Customer (debtor, with fuzzy match fields + merge_history JSONB)
  app/models/invoice.py   — Invoice (core record, 8 statuses, recovery tracking, data lineage, 4 composite indexes)
  app/models/import_record.py — ImportRecord (full audit trail, change_set JSONB for rollback, cost tracking)
  app/models/import_template.py — ImportTemplate (saved column mappings, format hints: decimal_separator + thousands_separator, usage counter). CHANGED in session 6: replaced number_format with explicit separator fields, updated comments to multilingual examples.
  app/models/activity.py  — Activity (timeline of all events, flexible JSONB details, 4 indexes)
  app/routers/upload.py     — POST /upload endpoint: thin wrapper over ingestion service, accepts CSV/TSV/XLSX multipart upload.
  app/routers/webhooks.py — Resend inbound webhook, attachment listing + download logging
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
  tests/test_file_parser.py   — 74 tests covering 5 fixtures + inline edge cases (comma+dot, plain dot, ID protection, .xls rejection, empty file, header-only, TSV)
  tests/test_column_mapper.py — 48 tests: 5 fixture mappings (all deterministic, LLM patched to verify never called), template validation + enrichment, mocked LLM fallback, hallucination rejection, conflict resolution, amount fallback, type-compatible candidate preference, partial-match guard, success=False on zero mappings.
  tests/test_ingestion.py   — Service-level ingestion tests: all 5 fixtures, hash, serialization, template pass-through, error handling.
  tests/test_upload.py      — HTTP endpoint tests: upload success, file validation, response shape, hash verification.
  Dockerfile            — Python 3.12-slim backend image for Railway (production). Local dev/test runs Python 3.14.3.
  railway.toml          — Railway deploy config
  requirements.txt      — all backend deps
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
  README.md              — documents all edge cases, format coverage matrix, and European scope. CHANGED in session 6: full rewrite.
BUILD_LOG.md            — this file
README.md               — project overview
.gitignore              — Python + Node + env files
```

---

## Session History

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
| 3 | Postmark for inbound + outbound email | One provider, best deliverability | 2026-03-19 |
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

---

## Open Bugs

- `backend/app/routers/webhooks.py` — `RESEND_WEBHOOK_SECRET` exists in config but the inbound webhook does not verify webhook signatures yet. Repro: `POST /webhooks/resend/inbound` with `{"type":"email.received","data":{...}}`. Severity: High.
- `backend/app/main.py` — `GET /test-email` is publicly reachable on the live backend and hardcodes `lorenzo.massimo.pandolfo@gmail.com` as the recipient. Repro: call `/test-email`. Severity: Medium.
- `backend/app/routers/webhooks.py` — inbound attachments are downloaded in memory and logged, but not persisted to disk, object storage, or the database. Repro: send an inbound email with an attachment; the bytes are discarded after the request completes. Severity: Medium.

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
> **Milestone 2 is done when:**
> - [x] CSV files parse correctly (comma and semicolon delimited) — verified across 5 fixtures
> - [ ] XLSX files parse correctly — implemented but not yet validated with a real XLSX fixture
> - [x] Encoding detection works for UTF-8 and Windows-1252 — verified by pohoda/fakturoid/messy/italian (UTF-8) and french (Windows-1252) fixtures
> - [ ] Encoding detection works for Windows-1250, ISO-8859-1, ISO-8859-15, ISO-8859-2 — implemented as fallbacks but not yet proven by fixture
> - [x] Column mapping works deterministically for known formats and falls back to LLM for unknown ones — verified across 5 fixtures spanning CZ/EN/FR/IT, LLM path tested with mocked provider, 48 tests
> - [ ] At least 5 export formats parse correctly — validated with 5 synthetic fixtures; real customer exports still needed during pilot
> - [ ] Email ingestion wrapper feeds attachments into the same pipeline as manual upload
> - [x] Manual upload endpoint accepts CSV/XLSX and returns parsed results — POST /upload returns full parse + mapping preview
> - [ ] Both ingestion paths produce identical results for the same file

---

## Queued Items (non-blocking)

| Item | Target Milestone | Notes |
|------|-----------------|-------|
| Change Account defaults: currency CZK → EUR, timezone Europe/Prague → Europe/Paris | M4 (Core UI) | Onboarding should detect locale and suggest defaults |
| Update `company_id` comment from "IČO in Czech" to generic "company registration number" | Next schema pass | Cosmetic but signals correct mental model |
| Add Italian to required reminder template languages | M5 (Action Execution) | FR/IT are primary markets; Italian must be first-class |
| Rotate Railway PostgreSQL password | ASAP | Public URL with credentials used in terminal session during migration |
| Create XLSX test fixture | M2 (next sub-task) | XLSX parsing path implemented but needs validation |

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
