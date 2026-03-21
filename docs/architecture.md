# Architecture Decision Record — Overdue Cash Control

**Version:** 1.0  
**Date:** March 2026  
**Author:** Lorenzo Pandolfo + Claude (AI architect)

---

## Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | Python 3.12 + FastAPI | Lorenzo's comfort language. Async support. Rich file-parsing ecosystem (pandas, openpyxl, chardet). |
| Frontend | Next.js 14 + Tailwind CSS + shadcn/ui | Fast to build, clean defaults. App Router with server components for dashboard. |
| Database | PostgreSQL 16 (Railway managed) | Relational, well-defined data model. JSONB for flexible import metadata. Managed backups, SSL, connection pooling. |
| ORM | SQLAlchemy 2.0 (async) | Mature, well-documented. Async via asyncpg driver. Alembic for migrations. |
| Hosting | Railway | Backend, frontend, PostgreSQL, and future worker processes in one platform. Auto-deploy from GitHub main branch. Zero DevOps. |
| LLM — Primary | OpenAI API (gpt-4o-mini) | Column mapping on unknown files, fuzzy customer matching. Deterministic matching is primary; LLM is fallback only. |
| LLM — Fallback | DeepSeek API (deepseek-chat) | Cost-effective fallback. OpenAI-compatible API — same SDK, different base_url. |
| Email — Outbound | Resend | Sends reminders from custom domain (noreply@overduecash.com). SPF/DKIM via Cloudflare auto-config. |
| Email — Inbound | Resend | Receives AR exports via webhook. Inbound address: tuaentoocl.resend.app. Attachments downloaded via Resend Attachments API. |
| DNS / CDN | Cloudflare | Domain registrar and DNS for overduecash.com. Free tier. Auto-configured DKIM/SPF for Resend. |
| Auth | Simple auth M4, hardening M8 | Email+password with bcrypt + JWT built in M4 (Core UI). Auth hardening (verification, rate limiting, data isolation) in M8 (Security & Trust). |
| Coding assistant | OpenAI Codex extension in VS Code | GPT-5.4, agent mode. Primary interface for writing and editing code. |
| Version control | GitHub (private repo) | CI/CD via Railway auto-deploy from main. |

---

## Project Structure

```
overdue-cash-control/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, route registration
│   │   ├── config.py            # pydantic-settings, env var loading
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── models/              # SQLAlchemy ORM models (M2+)
│   │   ├── routers/
│   │   │   └── webhooks.py      # Resend inbound email webhook
│   │   ├── services/
│   │   │   └── llm_client.py    # OpenAI primary, DeepSeek fallback
│   │   └── utils/
│   ├── alembic/                 # Database migrations
│   ├── tests/
│   ├── Dockerfile
│   ├── railway.toml
│   └── requirements.txt
├── frontend/
│   ├── src/app/                 # Next.js App Router pages
│   ├── Dockerfile
│   └── package.json
├── docs/                        # Product and architecture docs
├── sample-data/                 # Synthetic AR export files for testing
├── BUILD_LOG.md                 # Session continuity file
└── README.md
```

---

## Railway Architecture

```
Railway Project: overdue-cash-control
├── Service: backend     (FastAPI, Dockerfile, port 8080)
│   └── Root directory: /backend
├── Service: frontend    (Next.js, Dockerfile, port 3000)
│   └── Root directory: /frontend
├── Service: worker      (future — scheduled tasks, M6/M7)
└── Database: PostgreSQL (managed, attached to backend)
```

---

## LLM Integration Design

```
Column Mapping / Fuzzy Match Request
        │
        ▼
┌─────────────────────┐
│ Deterministic Match  │  ← Dictionary of known headers (CZ, DE, FR, EN, ES)
│ (no API call)        │    + saved Import Templates
└─────────┬───────────┘
          │ confidence < threshold
          ▼
┌─────────────────────┐
│ OpenAI API           │  ← gpt-4o-mini (cheap, fast)
│ (primary LLM)        │    Send: headers + 3 sample rows
└─────────┬───────────┘    Return: confidence-scored mapping
          │ API error / timeout
          ▼
┌─────────────────────┐
│ DeepSeek API         │  ← deepseek-chat, OpenAI-compatible
│ (fallback LLM)       │    Same prompt, same SDK
└─────────────────────┘
```

The LLM client (services/llm_client.py) exposes a single async function. The rest of the codebase never knows which provider answered. Switching models or adding providers is a one-file change.

---

## Email Architecture

### Outbound (reminders to debtors)

Two permanently first-class sending paths:

- **Model A (custom domain):** Resend sends from collections@clientcompany.com (or similar). Customer adds SPF/DKIM DNS records. Setup is optional and never blocks any feature.
- **Model B (draft-and-send):** Product generates complete email. User copies to their own email client. Always available, never degraded.

### Inbound (receiving AR exports)

- Each account gets a unique ingestion address (via Resend .resend.app domain for v1, custom subdomain later).
- Resend receives email, sends webhook POST to /webhooks/resend/inbound with metadata.
- Backend calls Resend Attachments API to get download URLs, downloads CSV/XLSX files.
- Files feed into the ingestion pipeline (M2).

---

## Data Flow

```
Email with CSV/XLSX attachment
        │
        ▼
┌─────────────────────┐
│ Resend Webhook       │  → POST /webhooks/resend/inbound
└─────────┬───────────┘
          │                    ┌──────────────────┐
          ├───── OR ──────────▶│ Manual Upload API │
          │                    └────────┬─────────┘
          ▼                             ▼
┌─────────────────────────────────────────┐
│ Ingestion Pipeline (identical for both) │
│  parse → map → normalise → preview      │
└─────────────────┬───────────────────────┘
                  ▼
┌─────────────────────┐
│ Preview Before Commit │  ← User reviews, confirms or cancels
└─────────────────┬───────┘
                  ▼
┌─────────────────────┐
│ Database (PostgreSQL) │  ← Invoices, customers, activity log
└─────────────────────┘
```

---

## Security Model (v1)

- HTTPS everywhere (Railway default)
- Database encryption at rest (Railway managed)
- Imported files stored encrypted (M3)
- No sensitive data in logs
- Webhook signature verification (Resend signing secret — open bug, to be fixed in M2)
- Single-user accounts in v1 (no multi-user, no roles)
- Auth hardening deferred to M10

---

## Key Design Principles

1. **Upload-first ingestion.** Manual upload is the guaranteed path. Email is a convenience wrapper over the same pipeline. This is an engineering guarantee, not a UX hierarchy — both paths are presented as first-class to the user (see product definition §2.1).
2. **Preview-before-commit.** Every import shows what will change before touching live data.
3. **Deterministic-first AI.** Saved templates and rule-based matching are primary. LLM is fallback for ambiguity only.
4. **Pre-generated actions.** Every queue item arrives with a ready-to-execute action. The user reviews and confirms, not composes from scratch.
5. **Smart defaults.** Zero configuration to start. Escalation rules, templates, and digests are pre-configured.
6. **Honest ROI.** Money-recovered counter tracks "recovered after active chasing" — not causal proof.

---

## What This Architecture Does NOT Include

- No API integrations with accounting tools (deferred to v1.2+)
- No PDF parsing (CSV and XLSX only for v1)
- No mobile app (responsive web only)
- No multi-language UI (English only; reminder templates multi-language)
- No multi-user accounts (single login per account)
- No automated sending without user confirmation
