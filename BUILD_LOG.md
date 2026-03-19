# BUILD LOG — Overdue Cash Control

## Current State
- **Milestone:** 1 — Architecture & Stack Lock
- **Session:** 1
- **Status:** Scaffold deployed
- **Last updated:** 2026-03-19

## What Exists
- GitHub repo created
- Project structure scaffolded
- FastAPI backend with /health endpoint
- Next.js frontend with landing page
- Dockerfiles for both services
- Railway config files

## What Was Built Last Session
- Initial scaffold (first session)

## What's Next
- Deploy backend + frontend to Railway
- Provision PostgreSQL on Railway
- Verify health check returns {"status": "ok", "db": "connected"}
- Set up Postmark account
- Wire inbound email webhook
- Test outbound email sending

## Open Bugs
- (none yet)

## Architecture Decisions
- Python/FastAPI backend (Lorenzo's comfort language)
- OpenAI primary LLM, DeepSeek fallback
- Postmark for both inbound and outbound email
- Railway for all hosting
- Auth deferred to Milestone 10 (simple JWT for now)
- See docs/architecture.md for full details

## Accounts Created
- [ ] GitHub repo: (your URL)
- [ ] Railway project: (pending)
- [ ] OpenAI API key: (pending)
- [ ] DeepSeek API key: (pending)
- [ ] Postmark account: (pending)

## Environment URLs
- Backend: (pending Railway deploy)
- Frontend: (pending Railway deploy)
- Database: (pending Railway provision)
