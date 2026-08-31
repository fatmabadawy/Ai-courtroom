"""
backend/app/api/main.py
────────────────────────
FastAPI application factory for Member E's API layer.

Architecture:
  Frontend → API → trial_service / evidence_service → graph / rag interface
                                                     → database adapter

CORS, lifespan, error handling, and all routers are assembled here.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.config import get_settings
from backend.app.api.database.adapter import init_db
from backend.app.api.routers import auth, cases, documents, evidence, n8n_internal, trial

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise the database on startup."""
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Courtroom API",
        description=(
            "Evidence-Based Multi-Agent Debate System — Member E API layer.\n\n"
            "This API is the integration point between the React frontend and the "
            "shared agent interfaces (Members A/B/C/D)."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error_code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": None,
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth.router)
    app.include_router(cases.router)
    app.include_router(documents.router)
    app.include_router(trial.router)
    app.include_router(evidence.router)
    app.include_router(n8n_internal.router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "mock_graph": settings.use_mock_graph,
            "mock_rag": settings.use_mock_rag,
            "db_backend": settings.db_backend,
        }

    return app


app = create_app()
