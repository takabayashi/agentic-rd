"""HTTP layer for the triage dashboard: routes, view helpers, and templates.

A single web module (the domain lives in `models`, data access in
`repository`). `main.py` builds the app and includes this router.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from .models import EditView, Label, select_edits
from .repository import DatabaseUnavailable, get_recent_edits

router = APIRouter()

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


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, label: str | None = None) -> HTMLResponse:
    try:
        all_edits = get_recent_edits()
    except DatabaseUnavailable:
        return templates.TemplateResponse(request, "warming_up.html", status_code=503)
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


@router.get("/api/edits")
def api_edits(label: str | None = None):
    """Classified edits as JSON, newest-highest-confidence first.

    Query param ``label`` (one of all|vandalism|substantive|trivia|unclear)
    filters the result; omitting it (or ``all``) returns everything. Returns
    503 while the database is warming up.
    """

    try:
        edits = get_recent_edits()
    except DatabaseUnavailable:
        return JSONResponse(status_code=503, content={"detail": "database warming up"})
    return select_edits(edits, label)


@router.get("/healthz")
def healthz() -> JSONResponse:
    # Liveness only — deliberately DB-independent so the app reports healthy and
    # can serve the 503 warm-up page even before Postgres is reachable.
    return JSONResponse(status_code=200, content={"status": "healthy"})
