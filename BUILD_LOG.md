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

- **Milestone:** 2 of 12 — Ingestion Engine (upload-first)
- **Sub-task:** File parsing engine — CSV/XLSX parser with encoding detection
- **Status:** All 7 database tables created and migrated to production PostgreSQL (accounts, users, customers, invoices, import_records, import_templates, activities). Ready to build the parsing and column mapping logic.
- **Blockers:** None
- **Last session:** 2026-03-20

---

## What Exists (file inventory)

```
backend/
  app/main.py           — FastAPI app, /, /health, /test-email, CORS, webhook router
  app/config.py         — env var loading for DB, LLM, Resend, auth, frontend
  app/database.py       — async SQLAlchemy engine + session
  app/services/llm_client.py — OpenAI primary, DeepSeek fallback
  app/models/__init__.py  — imports all 7 models for Alembic
  app/models/account.py   — Account (company using the product)
  app/models/user.py      — User (person logging in, separate for future multi-user)
  app/models/customer.py  — Customer (debtor, with fuzzy match fields + merge_history JSONB)
  app/models/invoice.py   — Invoice (core record, 8 statuses, recovery tracking, data lineage, 4 composite indexes)
  app/models/import_record.py — ImportRecord (full audit trail, change_set JSONB for rollback, cost tracking)
  app/models/import_template.py — ImportTemplate (saved column mappings, format hints, usage counter)
  app/models/activity.py  — Activity (timeline of all events, flexible JSONB details, 4 indexes)
  app/routers/webhooks.py — Resend inbound webhook, attachment listing + download logging
  app/routers/__init__.py — routers package marker
  app/utils/__init__.py — utils package placeholder
  app/__init__.py       — app package marker
  app/services/__init__.py — services package marker
  alembic/versions/4a129036b96f_create_all_tables.py — initial migration creating all 7 tables
  alembic/env.py        — updated to import all models for autogenerate
  alembic/script.py.mako — Alembic revision template
  alembic.ini           — Alembic config
  tests/__init__.py     — tests package placeholder
  Dockerfile            — Python 3.12 slim backend image for Railway
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
sample-data/
  pohoda_ar_export.csv   — semicolon-delimited, Czech headers, DD.MM.YYYY dates, 15 invoices
  fakturoid_ar_export.csv — comma-delimited, English headers, ISO dates, EUR, 15 invoices
  messy_generic_export.csv — Czech headers, messy data, missing fields, Czech number formatting, 12 invoices
  README.md              — documents every edge case for ingestion testing
BUILD_LOG.md            — this file
README.md               — project overview
.gitignore              — Python + Node + env files
```

---

## Session History

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
| 5 | Auth deferred to M10 | Simple JWT for now, proper auth later | 2026-03-19 |
| 6 | Codex in VS Code for code writing | GPT-5.4, agent mode, direct file editing | 2026-03-19 |
| 7 | Next.js App Router frontend | Fastest path to a minimal web UI that can deploy cleanly alongside the FastAPI backend on Railway | 2026-03-19 |
| 8 | Switched email provider from Postmark to Resend | Faster path to a working inbound webhook and outbound test flow during Milestone 1; Resend was simpler to debug live on Railway | 2026-03-20 |
| 9 | Separated User from Account tables | Prevents painful migration when multi-user arrives post-launch; costs one extra table now vs risky data migration later | 2026-03-20 |
| 10 | SQLAlchemy 2.0.48 (upgraded from 2.0.36) | Python 3.14 compatibility — 2.0.36 had a Union type bug with 3.14 | 2026-03-20 |
| 11 | Soft deletes on Invoice and Customer | Financial data should never be hard-deleted; nullable deleted_at column | 2026-03-20 |
| 12 | JSONB for change_set, merge_history, activity details | Flexibility without creating dozens of tables; sufficient for v1, can normalize later if needed | 2026-03-20 |

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
> - [ ] Files parse correctly: CSV (comma and semicolon delimited) and XLSX
> - [ ] Encoding detection works (UTF-8, Windows-1250, ISO-8859-2)
> - [ ] Column mapping works deterministically for known formats and falls back to LLM for unknown ones
> - [ ] At least 5 real-world export formats parse correctly (3 synthetic samples + 2 more during M2)
> - [ ] Email ingestion wrapper feeds attachments into the same pipeline as manual upload
> - [ ] Manual upload endpoint accepts CSV/XLSX and returns parsed results
> - [ ] Both ingestion paths produce identical results for the same file

---

## Reference Docs

The full product spec lives in these docs (paste relevant sections when needed, not every session):
- **Product constitution** (`docs/constitution.md`) — governing principles, decision filter, beachhead definition, pricing, exclusions
- **Wedge definition v1** — what the product does and doesn't do
- **Product definition** — NOT YET WRITTEN — screen-by-screen UX flow, to be created during M5
- **Build trajectory** — all 12 milestones, session plans, exit gates
- **Buyer analysis** — harsh buyer assessment with pricing signals, shared during M1 close-out

---

## For the AI: How to Read This Log

1. Read **Current State** to know where we are
2. Read **What Exists** to know what files are in the repo
3. Read **Session History** (last 2-3 entries) to know recent context
4. Read **Open Bugs** before writing new code
5. Check **Decisions Made** before proposing architecture changes
6. When the session ends, Lorenzo will ask you to update this file — follow the instructions below
7. When Claude generates a Codex prompt, always include `git add . && git commit -m "..." && git push origin main` at the end if files were changed. Codex handles git directly.

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
