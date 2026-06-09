"""Repository seam tests (parameterized SQL, no live database)."""

from unittest.mock import MagicMock, patch

import pytest
from psycopg import OperationalError
from triage import repository
from triage.repository import DatabaseUnavailable, check_ready, get_recent_edits


def test_select_recent_uses_parameterized_limit():
    """SQL must use a bound parameter, not string interpolation."""

    assert "%s" in repository._SELECT_RECENT
    assert "LIMIT %s" in repository._SELECT_RECENT
    assert "{" not in repository._SELECT_RECENT


class _FakeCursor:
    def __init__(self, captured):
        self._captured = captured

    def execute(self, sql, params=None):
        self._captured.append((sql, params))

    def fetchall(self):
        return []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _fake_pool(captured):
    fake_conn = MagicMock()
    fake_conn.cursor.return_value = _FakeCursor(captured)
    fake_conn.__enter__ = lambda self: self
    fake_conn.__exit__ = lambda self, *a: False
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = fake_conn
    return pool


def test_get_recent_edits_passes_limit_as_query_parameter():
    captured: list[tuple[str, tuple]] = []
    with patch.object(repository, "_get_pool", return_value=_fake_pool(captured)):
        get_recent_edits(limit=42)

    assert captured
    sql, params = captured[0]
    assert sql.strip() == repository._SELECT_RECENT.strip()
    assert params == (42,)


def test_get_recent_edits_maps_operational_error_to_database_unavailable():
    pool = MagicMock()
    pool.connection.side_effect = OperationalError("down")
    with patch.object(repository, "_get_pool", return_value=pool):
        with pytest.raises(DatabaseUnavailable):
            get_recent_edits()


def test_check_ready_true_when_reachable():
    with patch.object(repository, "_get_pool", return_value=_fake_pool([])):
        assert check_ready() is True


def test_check_ready_false_when_db_down():
    pool = MagicMock()
    pool.connection.side_effect = OperationalError("down")
    with patch.object(repository, "_get_pool", return_value=pool):
        assert check_ready() is False
