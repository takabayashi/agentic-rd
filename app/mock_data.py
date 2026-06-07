"""Hardcoded edit fixture for Phase 2 (no DB, no pipeline yet).

`load_edits()` is the seam the web layer depends on; Phase 3 replaces this
module's implementation with a Postgres-backed repository without touching the
routes. The fixture covers all four labels plus an escalated row so the UI can
be validated end-to-end. Set ``AGENTIC_EMPTY=1`` to exercise the empty state.
"""

import os
from datetime import UTC, datetime

from models import EditView, Label

_NOW = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


_MOCK_EDITS: list[EditView] = [
    EditView(
        rev_id=1300000001,
        title="Python (programming language)",
        editor="HelpfulEditor",
        comment="Expanded the section on the standard library with sourced examples.",
        label=Label.substantive,
        confidence=0.94,
        escalated=False,
        size_delta=1842,
        uri="https://en.wikipedia.org/w/index.php?diff=1300000001",
        event_ts=_NOW,
        classified_at=_NOW,
    ),
    EditView(
        rev_id=1300000002,
        title="List of common misconceptions",
        editor="192.0.2.51",
        comment="POOP POOP POOP haha you cant stop me",
        label=Label.vandalism,
        confidence=0.97,
        escalated=False,
        size_delta=-512,
        uri="https://en.wikipedia.org/w/index.php?diff=1300000002",
        event_ts=_NOW,
        classified_at=_NOW,
    ),
    EditView(
        rev_id=1300000003,
        title="Cricket World Cup",
        editor="StatsBotHelper",
        comment="Fixed a typo in the 1996 final attendance figure.",
        label=Label.trivia,
        confidence=0.81,
        escalated=False,
        size_delta=3,
        uri="https://en.wikipedia.org/w/index.php?diff=1300000003",
        event_ts=_NOW,
        classified_at=_NOW,
    ),
    EditView(
        rev_id=1300000004,
        title="Quantum entanglement",
        editor="203.0.113.7",
        comment="rewrote intro",
        label=Label.unclear,
        confidence=0.41,
        escalated=True,
        size_delta=220,
        uri="https://en.wikipedia.org/w/index.php?diff=1300000004",
        event_ts=_NOW,
        classified_at=_NOW,
    ),
    EditView(
        rev_id=1300000005,
        title="Eiffel Tower",
        editor="CuriousNewbie",
        comment="Updated the visitor count for 2025 and added a citation.",
        label=Label.substantive,
        confidence=0.62,
        escalated=True,
        size_delta=95,
        uri="https://en.wikipedia.org/w/index.php?diff=1300000005",
        event_ts=_NOW,
        classified_at=_NOW,
    ),
]


def load_edits() -> list[EditView]:
    """Return the current set of classified edits. Honors ``AGENTIC_EMPTY`` so
    the empty-state view can be demoed without code changes."""

    if os.getenv("AGENTIC_EMPTY") == "1":
        return []
    return list(_MOCK_EDITS)
