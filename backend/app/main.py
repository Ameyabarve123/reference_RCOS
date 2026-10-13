import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="RCOS RAG API",
    description="Ingestion, pgvector retrieval, and Gemini answers for the RCOS RAG application.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health() -> dict[str, bool | str]:
    return {
        "status": "ok",
        "supabase": bool(settings.supabase_url and settings.supabase_key),
        "gemini": bool(settings.google_api_key),
    }
