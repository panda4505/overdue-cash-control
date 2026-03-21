# Overdue Cash Control

Collections workflow for EU SMBs. Import your receivables, get a daily action queue, chase overdue invoices until cash arrives.

## Stack

- **Backend:** Python + FastAPI
- **Frontend:** Next.js 14 + Tailwind + shadcn/ui
- **Database:** PostgreSQL 16 (Railway managed)
- **Hosting:** Railway
- **LLM:** OpenAI (primary) + DeepSeek (fallback)
- **Email:** Postmark (inbound + outbound)

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

## Deployment

Both services auto-deploy from `main` via Railway.
