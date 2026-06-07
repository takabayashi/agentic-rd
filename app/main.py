"""Wikipedia Edit-Triage Agent — web app.

Phase 2: a moderator dashboard fed by a hardcoded fixture (`mock_data`). The
data source is swapped for Postgres in Phase 3 without changing these routes.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from mock_data import load_edits
from models import EditView, Label, select_edits

app = FastAPI(title="Wikipedia Edit-Triage Agent", version="0.0.0")

# Jinja2 autoescaping is ON by default for .html templates — required because
# edit titles and comments are attacker-controllable free text.
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# Filter chips: "all" plus every label in the enum (single source of truth).
FILTERS: list[str] = ["all", *[label.value for label in Label]]


def _label_counts(edits: list[EditView]) -> dict[str, int]:
    counts = {"all": len(edits)}
    for label in Label:
        counts[label.value] = sum(1 for e in edits if e.label is label)
    return counts


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, label: str | None = None) -> HTMLResponse:
    all_edits = load_edits()
    active = label if label in FILTERS else "all"
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "edits": select_edits(all_edits, active),
            "filters": FILTERS,
            "counts": _label_counts(all_edits),
            "active": active,
        },
    )


@app.get("/api/edits")
def api_edits(label: str | None = None) -> list[EditView]:
    """Classified edits as JSON, newest-highest-confidence first.

    Query param ``label`` (one of all|vandalism|substantive|trivia|unclear)
    filters the result; omitting it (or ``all``) returns everything.
    """

    return select_edits(load_edits(), label)


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "healthy"})
