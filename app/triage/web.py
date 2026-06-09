"""HTTP layer for the triage dashboard: routes and view helpers.

A single web module (the domain lives in `models`, data access in `repository`,
HTML rendering in `render`). `main.py` builds the app and includes this router.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from .models import EditView, Label, select_edits
from .render import render_dashboard, render_warming_up
from .repository import DatabaseUnavailable, get_recent_edits

router = APIRouter()

# Filter chips: "all" plus every label in the enum (single source of truth).
FILTERS: list[str] = ["all", *[label.value for label in Label]]


def _label_counts(edits: list[EditView]) -> dict[str, int]:
    counts = {"all": len(edits)}
    for label in Label:
        counts[label.value] = sum(1 for e in edits if e.label is label)
    return counts


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.lower() in ("1", "true", "yes", "on")


@router.get("/", response_class=HTMLResponse)
def dashboard(label: str | None = None, escalated: str | None = None) -> HTMLResponse:
    try:
        all_edits = get_recent_edits()
    except DatabaseUnavailable:
        return HTMLResponse(render_warming_up(), status_code=503)
    active = label if label in FILTERS else "all"
    escalated_active = _is_truthy(escalated)
    newest = max((e.classified_at for e in all_edits), default=None)
    return HTMLResponse(
        render_dashboard(
            edits=select_edits(all_edits, active, escalated_only=escalated_active),
            filters=FILTERS,
            counts=_label_counts(all_edits),
            active=active,
            escalated_active=escalated_active,
            escalated_count=sum(1 for e in all_edits if e.escalated),
            newest_classified_at=newest,
        )
    )


@router.get("/api/edits")
def api_edits(label: str | None = None, escalated: str | None = None):
    """Classified edits as JSON, newest-highest-confidence first.

    Query param ``label`` (one of all|vandalism|substantive|trivia|unclear)
    filters the result; ``escalated=1`` narrows to escalated (pass-2) rows.
    Omitting both returns everything. Returns 503 while the database is warming up.
    """

    try:
        edits = get_recent_edits()
    except DatabaseUnavailable:
        return JSONResponse(status_code=503, content={"detail": "database warming up"})
    return select_edits(edits, label, escalated_only=_is_truthy(escalated))


@router.get("/healthz")
def healthz() -> JSONResponse:
    # Liveness only — deliberately DB-independent so the app reports healthy and
    # can serve the 503 warm-up page even before Postgres is reachable.
    return JSONResponse(status_code=200, content={"status": "healthy"})
