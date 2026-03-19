# BUILD LOG — Overdue Cash Control

> **Purpose:** Paste this entire file at the start of every AI session
> (Claude, Codex, or any other). It is the single source of truth for
> what exists, what works, what's broken, and what's next.

---

## Identity

- **Product:** Overdue Cash Control — collections workflow for EU SMBs
- **Builder:** Lorenzo (founder, tester, decision-maker)
- **AI engineer:** Codex in VS Code (code writing) + Claude (architecture, planning, reviews)
- **Stack:** Python/FastAPI backend, Next.js frontend, PostgreSQL on Railway, OpenAI + DeepSeek LLM, Postmark email
- **Repo:** https://github.com/panda4505/overdue-cash-control

---

## Current State

- **Milestone:** 1 of 12 — Architecture & Stack Lock
- **Sub-task:** Postmark setup + email flow
- **Status:** FastAPI backend is live on Railway with PostgreSQL connected; Next.js frontend is live; `/health` returns `{"status":"ok","db":"connected","version":"0.1.0"}`
- **Blockers:** Postmark account not yet created, so inbound/outbound email work has not started
- **Last session:** 2026-03-19

---

## What Exists (file inventory)

```
backend/
  app/main.py           — FastAPI app, /, /health endpoint, CORS
  app/config.py         — pydantic-settings, env var loading
  app/database.py       — async SQLAlchemy engine + session
  app/services/llm_client.py — OpenAI primary, DeepSeek fallback
  app/models/__init__.py — models package placeholder
  app/routers/__init__.py — routers package placeholder
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

---

## Open Bugs

(none yet)

---

## Accounts & URLs

| Service | Status | URL / Notes |
|---------|--------|-------------|
| GitHub repo | ✅ Created | https://github.com/panda4505/overdue-cash-control |
| Railway project | ✅ Created | Backend + frontend services are live |
| Railway PostgreSQL | ✅ Connected | Attached to backend; `/health` reports `db=connected` |
| Backend deploy | ✅ Live | Railway URL not recorded in this log yet |
| Frontend deploy | ✅ Live | Railway URL not recorded in this log yet |
| OpenAI API key | ⬜ Not added | — |
| DeepSeek API key | ⬜ Not added | — |
| Postmark account | ⬜ Not started | Next session task |
| Product domain | ⬜ Deferred | Using Railway URLs for now |

---

## Current Milestone Exit Gate

> **Milestone 1 is done when:**
> - [x] Backend deployed to Railway, /health returns {"status":"ok","db":"connected"}
> - [x] Frontend deployed to Railway, page loads
> - [x] PostgreSQL provisioned and connected
> - [ ] Postmark inbound webhook receives email + extracts attachment
> - [ ] Postmark outbound sends from custom domain, arrives in inbox (not spam)
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
