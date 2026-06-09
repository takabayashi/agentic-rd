"""Wikipedia Edit-Triage Agent — application composition root.

Builds the FastAPI app and wires in the web layer, request metrics, and
structured JSON logging. The dashboard reads classified edits from Postgres via
the repository; if the database isn't ready (cold start) or is transiently
down, requests degrade to a 503 warm-up response instead of crashing.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .logging_config import configure_logging
from .metrics import metrics_middleware
from .repository import close_pool
from .web import router

# Dashboard assets (CSS/JS) live as real files under app/static and are served
# at /static, so the markup links them with <link>/<script src> instead of
# inlining. Resolved relative to this file so it works regardless of CWD.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logging.getLogger("triage").info("application starting")
    yield
    close_pool()


app = FastAPI(title="Wikipedia Edit-Triage Agent", version="0.0.0", lifespan=lifespan)
app.middleware("http")(metrics_middleware)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(router)
