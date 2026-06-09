"""HTTP layer for the triage dashboard: routes and view helpers.

A single web module (the domain lives in `models`, data access in `repository`,
HTML rendering in `render`). `main.py` builds the app and includes this router.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .metrics import metrics_response
from .models import EditView, Label, select_edits
from .render import render_dashboard, render_feed, render_rows, render_warming_up
from .repository import DatabaseUnavailable, check_ready, get_recent_edits

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


def _selected_recent(
    all_edits: list[EditView], label: str | None, escalated: str | None
) -> list[EditView]:
    """The filtered list ordered newest-first — the feed's full window, which the
    renderer pages through for infinite scroll."""

    active = label if label in FILTERS else "all"
    return select_edits(all_edits, active, escalated_only=_is_truthy(escalated), order="recent")


def _render_kwargs(all_edits: list[EditView], label: str | None, escalated: str | None) -> dict:
    """Shared view-model assembly for the full page and the live fragment."""

    active = label if label in FILTERS else "all"
    escalated_active = _is_truthy(escalated)
    return dict(
        edits=_selected_recent(all_edits, label, escalated),
        filters=FILTERS,
        counts=_label_counts(all_edits),
        active=active,
        escalated_active=escalated_active,
        escalated_count=sum(1 for e in all_edits if e.escalated),
        newest_classified_at=max((e.classified_at for e in all_edits), default=None),
    )


@router.get("/", response_class=HTMLResponse)
def dashboard(label: str | None = None, escalated: str | None = None) -> HTMLResponse:
    try:
        all_edits = get_recent_edits()
    except DatabaseUnavailable:
        return HTMLResponse(render_warming_up(), status_code=503)
    return HTMLResponse(render_dashboard(**_render_kwargs(all_edits, label, escalated)))


@router.get("/fragment/edits", response_class=HTMLResponse)
def fragment_edits(label: str | None = None, escalated: str | None = None) -> HTMLResponse:
    """The dynamic dashboard region (stats + filters + table) the client poller
    swaps in. Returns 503 while the database is warming up so the poller can show
    the live indicator as offline."""

    try:
        all_edits = get_recent_edits()
    except DatabaseUnavailable:
        return HTMLResponse("<p class='sub'>database warming up…</p>", status_code=503)
    return HTMLResponse(render_feed(**_render_kwargs(all_edits, label, escalated)))


@router.get("/fragment/rows", response_class=HTMLResponse)
def fragment_rows(
    label: str | None = None, escalated: str | None = None, offset: int = 0
) -> HTMLResponse:
    """One infinite-scroll page of ``<tr>`` rows (plus the next-page sentinel),
    newest-first. The client appends this into the existing ``<tbody>`` as the
    user scrolls; the server stays the single source of row markup."""

    try:
        all_edits = get_recent_edits()
    except DatabaseUnavailable:
        return HTMLResponse("", status_code=503)
    selected = _selected_recent(all_edits, label, escalated)
    return HTMLResponse(render_rows(selected, max(offset, 0)))


@router.get("/api/edits", response_model=None)
def api_edits(
    label: str | None = None,
    escalated: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[EditView] | JSONResponse:
    """Classified edits as JSON, newest-highest-confidence first.

    Query param ``label`` (one of all|vandalism|substantive|trivia|unclear)
    filters the result; ``escalated=1`` narrows to escalated (pass-2) rows.
    ``limit``/``offset`` paginate the (already filtered+sorted) result; omitting
    ``limit`` returns the whole recent window. Returns 503 while the database is
    warming up.
    """

    try:
        edits = get_recent_edits()
    except DatabaseUnavailable:
        return JSONResponse(status_code=503, content={"detail": "database warming up"})
    selected = select_edits(edits, label, escalated_only=_is_truthy(escalated))
    if offset:
        selected = selected[offset:]
    if limit is not None:
        selected = selected[:limit]
    return selected


@router.get("/healthz")
def healthz() -> JSONResponse:
    # Liveness only — deliberately DB-independent so the app reports healthy and
    # can serve the 503 warm-up page even before Postgres is reachable.
    return JSONResponse(status_code=200, content={"status": "healthy"})


@router.get("/readyz")
def readyz() -> JSONResponse:
    # Readiness — checks the database is actually reachable. Distinct from
    # /healthz (liveness) so an orchestrator can hold traffic until the DB is up
    # without ever restarting an otherwise-healthy app during a cold start.
    if check_ready():
        return JSONResponse(status_code=200, content={"status": "ready"})
    return JSONResponse(status_code=503, content={"status": "not ready"})


@router.get("/metrics")
def metrics() -> Response:
    # Prometheus exposition (request counts + latency). Plain-text, unauthenticated
    # — local-only, like the rest of the stack.
    return metrics_response()
