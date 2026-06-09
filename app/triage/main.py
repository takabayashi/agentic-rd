"""Wikipedia Edit-Triage Agent — application composition root.

Builds the FastAPI app and wires in the web layer, request metrics, and
structured JSON logging. The dashboard reads classified edits from Postgres via
the repository; if the database isn't ready (cold start) or is transiently
down, requests degrade to a 503 warm-up response instead of crashing.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .logging_config import configure_logging
from .metrics import metrics_middleware
from .repository import close_pool
from .web import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logging.getLogger("triage").info("application starting")
    yield
    close_pool()


app = FastAPI(title="Wikipedia Edit-Triage Agent", version="0.0.0", lifespan=lifespan)
app.middleware("http")(metrics_middleware)
app.include_router(router)
