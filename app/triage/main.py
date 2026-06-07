"""Wikipedia Edit-Triage Agent — application composition root.

Builds the FastAPI app and wires in the web layer. The dashboard reads
classified edits from Postgres via the repository; if the database isn't ready
(cold start) or is transiently down, requests degrade to a 503 warm-up response
instead of crashing (see `triage/web/routes.py`).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .repository import close_pool
from .web import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    close_pool()


app = FastAPI(title="Wikipedia Edit-Triage Agent", version="0.0.0", lifespan=lifespan)
app.include_router(router)
