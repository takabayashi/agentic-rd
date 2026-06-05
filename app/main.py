"""Wikipedia Edit-Triage Agent — web app.

Phase 0: a minimal FastAPI service that proves the app starts cleanly and is
healthy. Real serving (dashboard, /api/edits) is added in later phases.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Wikipedia Edit-Triage Agent", version="0.0.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "healthy"})
