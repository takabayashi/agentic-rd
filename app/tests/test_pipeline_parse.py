"""Tests for pipeline parse/normalize logic (mirrors Connect Bloblang)."""

import pytest
from triage.pipeline_parse import (
    clamp_confidence,
    extract_json_blob,
    normalize_label,
    parse_llm_classification,
    parse_sse_data_line,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("vandalism", "vandalism"),
        ("  SUBSTANTIVE ", "substantive"),
        ("spam", "unclear"),
        ("", "unclear"),
        (None, "unclear"),
    ],
)
def test_normalize_label(raw, expected):
    assert normalize_label(raw) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.5, 0.5),
        (5, 1.0),
        (-2, 0.0),
        ("0.8", 0.8),
        ("nope", 0.0),
        (None, 0.0),
    ],
)
def test_clamp_confidence(value, expected):
    assert clamp_confidence(value) == expected


def test_extract_json_blob_from_prose_wrapped_response():
    raw = 'Here is my answer: {"label": "vandalism", "confidence": 0.9} thanks'
    assert extract_json_blob(raw) == '{"label": "vandalism", "confidence": 0.9}'


def test_parse_llm_classification_dirty_json():
    raw = 'Sure! {"label": "substantive", "confidence": 0.85}'
    assert parse_llm_classification(raw) == ("substantive", 0.85)


def test_parse_llm_classification_enum_drift():
    assert parse_llm_classification('{"label": "spam", "confidence": 0.99}') == (
        "unclear",
        0.99,
    )


def test_parse_llm_classification_malformed_defaults():
    assert parse_llm_classification("not json at all") == ("unclear", 0.0)
    assert parse_llm_classification("") == ("unclear", 0.0)


@pytest.mark.parametrize(
    "line",
    [
        ":ok",
        "event: heartbeat",
        "id: 1",
        "data: not-json",
        "data: :ok",
        "",
        "   ",
    ],
)
def test_parse_sse_data_line_drops_non_payload_frames(line):
    assert parse_sse_data_line(line) is None


def test_parse_sse_data_line_parses_valid_edit():
    line = 'data: {"type": "edit", "title": "Foo"}'
    assert parse_sse_data_line(line) == {"type": "edit", "title": "Foo"}
