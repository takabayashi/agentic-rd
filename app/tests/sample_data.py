"""Sample edits used by the test suite.

These mirror ``db/seed.sql`` and stand in for the Postgres repository so the
unit/route tests run without a live database (see ``conftest.py``). The set
covers all four labels plus escalated rows.
"""

from datetime import UTC, datetime

from triage.models import EditView, Label

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
    """Return the sample classified edits."""

    return list(_MOCK_EDITS)
