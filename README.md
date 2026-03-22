# Overdue Cash Control

Collections workflow for EU SMBs. Import your receivables, get a daily action queue, chase overdue invoices until cash arrives.

## Stack

- **Backend:** Python + FastAPI
- **Frontend:** Next.js 14 + Tailwind + shadcn/ui
- **Database:** PostgreSQL 16 (Railway managed)
- **Hosting:** Railway
- **LLM:** OpenAI (primary) + DeepSeek (fallback)
- **Email:** Resend (inbound + outbound)

## Local Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local  # Fill in API URL
npm run dev
```

## Documentation

| Document | Role |
|----------|------|
| `BUILD_LOG.md` | Current project state, decisions, test evidence |
| `docs/ai-engineering-workflow.md` | AI collaboration process and roles |
| `docs/README.md` | Docs map, reading order, update rules |
| `docs/opportunities.md` | Strategic discoveries not yet committed |
| `docs/trajectory.md` | Committed roadmap and milestones |
| `docs/product-definition.md` | Product spec (screens, data model, engines) |
| `docs/architecture.md` | Technical stack and design decisions |
| `docs/constitution.md` | Governing principles — highest authority |
| `docs/wedge-v1.md` | Commercial wedge scope and boundary |

## Deployment

Both services auto-deploy from `main` via Railway.
