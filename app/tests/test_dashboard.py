from datetime import UTC, datetime

import main
from fastapi.testclient import TestClient
from models import EditView, Label, select_edits

client = TestClient(main.app)

_TS = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)


def _edit(rev_id: int, label: Label, confidence: float, **kw) -> EditView:
    base = dict(
        rev_id=rev_id,
        title="Some Article",
        editor="Someone",
        comment="a comment",
        label=label,
        confidence=confidence,
        escalated=False,
        size_delta=10,
        uri="https://en.wikipedia.org/w/index.php?diff=" + str(rev_id),
        event_ts=_TS,
        classified_at=_TS,
    )
    base.update(kw)
    return EditView(**base)


def test_select_edits_sorts_by_confidence_desc():
    edits = [
        _edit(1, Label.trivia, 0.3),
        _edit(2, Label.vandalism, 0.9),
        _edit(3, Label.trivia, 0.6),
    ]
    result = select_edits(edits)
    assert [e.confidence for e in result] == [0.9, 0.6, 0.3]


def test_select_edits_filters_by_label():
    edits = [_edit(1, Label.vandalism, 0.9), _edit(2, Label.trivia, 0.6)]
    assert [e.rev_id for e in select_edits(edits, "vandalism")] == [1]
    assert len(select_edits(edits, "all")) == 2
    assert len(select_edits(edits, None)) == 2


def test_api_edits_returns_sorted_json():
    rows = client.get("/api/edits").json()
    assert len(rows) >= 4
    confidences = [r["confidence"] for r in rows]
    assert confidences == sorted(confidences, reverse=True)
    first = rows[0]
    assert set(first) == {
        "rev_id",
        "title",
        "editor",
        "comment",
        "label",
        "confidence",
        "escalated",
        "size_delta",
        "uri",
        "event_ts",
        "classified_at",
    }
    assert first["label"] in {"vandalism", "substantive", "trivia", "unclear"}
    # epoch is never serialized raw — datetimes come out as ISO strings
    assert "T" in first["event_ts"]


def test_api_edits_label_filter():
    rows = client.get("/api/edits", params={"label": "vandalism"}).json()
    assert rows and all(r["label"] == "vandalism" for r in rows)


def test_dashboard_renders_all_labels_and_escalation():
    html = client.get("/").text
    for label in ("vandalism", "substantive", "trivia", "unclear"):
        assert f"badge {label}" in html
    assert "escalated" in html


def test_dashboard_escapes_malicious_title(monkeypatch):
    evil = _edit(999, Label.vandalism, 0.5, title="<script>alert('xss')</script>")
    monkeypatch.setattr(main, "load_edits", lambda: [evil])
    html = client.get("/").text
    assert "<script>alert('xss')</script>" not in html
    assert "&lt;script&gt;" in html


def test_dashboard_empty_state(monkeypatch):
    monkeypatch.setattr(main, "load_edits", lambda: [])
    html = client.get("/").text
    assert "No edits to show" in html
