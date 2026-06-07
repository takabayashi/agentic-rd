"""Shared test fixtures.

The routes read from Postgres via ``triage.web.get_recent_edits``. To keep the
unit/route tests fast and DB-free, this autouse fixture swaps that repository
call for the in-memory sample set. Individual tests can re-patch
``triage.web.get_recent_edits`` to simulate other states (DB down, empty,
malicious input).
"""

import pytest
import sample_data
from triage import web


@pytest.fixture(autouse=True)
def mock_repo(monkeypatch):
    monkeypatch.setattr(web, "get_recent_edits", lambda *a, **k: sample_data.load_edits())
