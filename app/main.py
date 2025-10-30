from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from .database import Base, engine
from .routers import api, web
from .telegram_poller import start_polling

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):  # pragma: no cover - simple bootstrap hook
        Base.metadata.create_all(bind=engine)
        
        # Start Telegram polling in background
        polling_task = asyncio.create_task(start_polling())
        
        yield
        
        # Cancel polling when app shuts down
        polling_task.cancel()

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
