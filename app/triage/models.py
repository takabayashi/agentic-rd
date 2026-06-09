"""Domain model for the triage dashboard.

The view-model here is the stable contract the web layer renders and the
`/api/edits` endpoint serializes. Data sources (the Phase 2 mock fixture, the
Phase 3 Postgres repository) produce these objects; the web layer never sees
raw rows. Keeping the shape in one place means the UI and the pipeline schema
agree on exactly one definition.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class Label(StrEnum):
    """The fixed triage enum. The LLM output is normalized into this set so
    model drift / prompt-injection can't introduce new labels downstream."""

    vandalism = "vandalism"
    substantive = "substantive"
    trivia = "trivia"
    unclear = "unclear"


class EditView(BaseModel):
    """One classified edit as shown on the dashboard / returned by the API."""

    rev_id: int
    title: str
    editor: str
    comment: str
    label: Label
    confidence: float
    escalated: bool
    size_delta: int
    uri: str
    event_ts: datetime
    classified_at: datetime


def select_edits(
    edits: list[EditView],
    label: str | None = None,
    escalated_only: bool = False,
    order: str = "confidence",
) -> list[EditView]:
    """Filter by label (``None`` or ``"all"`` means no filter), optionally to
    escalated-only, and sort. ``order="recent"`` sorts newest-first (by
    ``classified_at``) for the infinite-scroll feed; the default ``"confidence"``
    sorts highest-confidence first. Pure function so it is trivially testable and
    shared by both the HTML view and the JSON API."""

    selected = edits
    if label and label != "all":
        selected = [e for e in selected if e.label.value == label]
    if escalated_only:
        selected = [e for e in selected if e.escalated]
    if order == "recent":
        return sorted(selected, key=lambda e: e.classified_at, reverse=True)
    return sorted(selected, key=lambda e: e.confidence, reverse=True)
