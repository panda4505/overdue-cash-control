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

- **Milestone:** 1 of 12 — Architecture & Stack Lock
- **Sub-task:** Architecture doc + sample AR file collection (last two exit gate items)
- **Status:** 6 of 8 Milestone 1 exit gates passed. Backend, frontend, PostgreSQL, outbound email, and inbound webhook with attachment download all live and proven. Remaining: architecture doc in docs/ and 3+ real AR export files in sample-data/.
- **Blockers:** None for M1 exit gate. Webhook signature verification and attachment persistence are open bugs carried into M2.
- **Last session:** 2026-03-20

---

## What Exists (file inventory)

```
backend/
  app/main.py           — FastAPI app, /, /health, /test-email, CORS, webhook router
  app/config.py         — env var loading for DB, LLM, Resend, auth, frontend
  app/database.py       — async SQLAlchemy engine + session
  app/services/llm_client.py — OpenAI primary, DeepSeek fallback
  app/models/__init__.py — models package placeholder
  app/routers/webhooks.py — Resend inbound webhook, attachment listing + download logging
  app/routers/__init__.py — routers package marker
  app/utils/__init__.py — utils package placeholder
  app/__init__.py       — app package marker
  app/services/__init__.py — services package marker
  alembic/env.py        — async migration runner
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
  .gitkeep              — placeholder; architecture doc still pending
sample-data/
  .gitkeep              — placeholder; need 3+ real AR exports
BUILD_LOG.md            — this file
README.md               — project overview
.gitignore              — Python + Node + env files
```

---

## Session History

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
| OpenAI API key | ⬜ Not added | — |
| DeepSeek API key | ⬜ Not added | — |
| Resend account | ✅ Created | Domain overduecash.com verified, inbound receiving via tuaentoocl.resend.app |
| Product domain | ✅ Registered | overduecash.com on Cloudflare, DNS verified by Resend |

---

## Current Milestone Exit Gate

> **Milestone 1 is done when:**
> - [x] Backend deployed to Railway, /health returns {"status":"ok","db":"connected"}
> - [x] Frontend deployed to Railway, page loads
> - [x] PostgreSQL provisioned and connected
> - [x] Resend inbound webhook receives email + extracts attachment — tested and confirmed: email to test@tuaentoocl.resend.app triggers POST to /webhooks/resend/inbound, Attachments API returns 200, CSV downloaded (911 bytes logged in Railway)
> - [x] Resend outbound sends from custom domain, arrives in inbox (not spam) — tested and confirmed: /test-email sends from noreply@overduecash.com via Resend API, arrived in Gmail inbox (not spam)
> - [ ] At least 3 real AR export files in sample-data/
> - [ ] Architecture doc committed to docs/
> - [x] This build log is accurate and current

---

## Reference Docs

The full product spec lives in these docs (paste relevant sections when needed, not every session):
- **Product constitution** — core principles, decision filters
- **Wedge definition v1** — what the product does and doesn't do
- **Build trajectory** — all 12 milestones, session plans, exit gates

---

## For the AI: How to Read This Log

1. Read **Current State** to know where we are
2. Read **What Exists** to know what files are in the repo
3. Read **Session History** (last 2-3 entries) to know recent context
4. Read **Open Bugs** before writing new code
5. Check **Decisions Made** before proposing architecture changes
6. When the session ends, Lorenzo will ask you to update this file — follow the instructions below

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
