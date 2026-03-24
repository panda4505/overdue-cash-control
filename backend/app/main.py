from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.routers.auth import router as auth_router
from app.routers.dashboard import router as dashboard_router
from app.routers.imports import router as imports_router, confirm_router
from app.routers.upload import router as upload_router
from app.routers.webhooks import router as webhooks_router

settings = get_settings()

app = FastAPI(
    title="Overdue Cash Control",
    description="Collections workflow for EU SMBs",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(webhooks_router)
app.include_router(upload_router)
app.include_router(imports_router)
app.include_router(confirm_router)
app.include_router(dashboard_router)


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
        "version": "0.2.0",
    }


@app.get("/")
async def root():
    return {"message": "Overdue Cash Control API", "docs": "/docs"}
