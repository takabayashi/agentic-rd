"""Pure-Python reference for Connect Bloblang parse/normalize logic.

Mirrors the classify ``result_map`` and ingest SSE frame handling in
``connect/classify.yaml`` and ``connect/ingest.yaml``. Kept in the app so the
highest-risk edge cases are testable without a Connect test harness; Connect
remains the runtime source of truth.
"""

from __future__ import annotations

import json
import re
from typing import Any

ALLOWED_LABELS = frozenset({"vandalism", "substantive", "trivia", "unclear"})

# First {...} block, non-greedy across newlines — same pattern as classify.yaml.
_JSON_BLOCK = re.compile(r"(?s)\{.*\}")


def normalize_label(raw: str | None) -> str:
    """Map a model label to the fixed enum; unknown/empty -> ``unclear``."""

    label = (raw or "").strip().lower()
    return label if label in ALLOWED_LABELS else "unclear"


def clamp_confidence(value: Any) -> float:
    """Coerce to float and clamp to [0, 1]; non-numeric -> 0."""

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if confidence < 0:
        return 0.0
    if confidence > 1:
        return 1.0
    return confidence


def extract_json_blob(text: str) -> str:
    """Return the first ``{...}`` substring, or ``"{}"`` if none."""

    match = _JSON_BLOCK.search(text)
    return match.group(0) if match else "{}"


def parse_llm_classification(raw: str) -> tuple[str, float]:
    """Parse a model reply into ``(label, confidence)``."""

    blob = extract_json_blob(raw)
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    return normalize_label(parsed.get("label")), clamp_confidence(parsed.get("confidence", 0))


def parse_sse_data_line(line: str) -> dict[str, Any] | None:
    """Parse one SSE line; return JSON object or ``None`` if the frame is dropped.

    Matches ingest.yaml: keep only ``data:`` lines, strip prefix, fail-closed on
  non-JSON (heartbeats, ``event:``, etc.).
    """

    text = line.strip()
    if not text or not text.startswith("data:"):
        return None
    payload = text.removeprefix("data:").strip()
    if not payload:
        return None
    try:
        value = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
