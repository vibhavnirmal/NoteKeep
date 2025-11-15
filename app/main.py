from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from .crud import ensure_default_tags
from .database import SessionLocal
from .routers import api, web

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # pragma: no cover - simple bootstrap hook
        # Database migrations are now handled by Alembic via migrate.py
        # This ensures proper schema versioning and backward compatibility
        with SessionLocal() as session:
            ensure_default_tags(session)
            session.commit()
        yield

    app = FastAPI(title="NoteKeep", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    app.include_router(api.router)
    app.include_router(web.router)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    return app


app = create_app()
