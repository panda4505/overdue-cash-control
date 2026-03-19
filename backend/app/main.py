from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
import httpx

from app.config import get_settings
from app.database import engine

settings = get_settings()

app = FastAPI(
    title="Overdue Cash Control",
    description="Collections workflow for EU SMBs",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    db_status = "disconnected"
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "db": db_status,
        "version": "0.1.0",
    }


@app.get("/")
async def root():
    return {"message": "Overdue Cash Control API", "docs": "/docs"}


@app.get("/test-email")
async def test_email():
    """Send a test email via Resend. Remove this endpoint after testing."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": "Overdue Cash Control <noreply@overduecash.com>",
                "to": "lorenzo.massimo.pandolfo@gmail.com",
                "subject": "Test — Overdue Cash Control is alive",
                "html": "<h1>It works!</h1><p>Outbound email from overduecash.com is working.</p>",
            },
        )
    return {"status": response.status_code, "body": response.json()}