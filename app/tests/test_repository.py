"""Repository seam tests (parameterized SQL, no live database)."""

from unittest.mock import MagicMock, patch

import pytest
from psycopg import OperationalError
from triage import repository
from triage.repository import DatabaseUnavailable, get_recent_edits


def test_select_recent_uses_parameterized_limit():
    """SQL must use a bound parameter, not string interpolation."""

    assert "%s" in repository._SELECT_RECENT
    assert "LIMIT %s" in repository._SELECT_RECENT
    assert "{" not in repository._SELECT_RECENT


def test_get_recent_edits_passes_limit_as_query_parameter():
    captured: list[tuple[str, tuple]] = []

    class FakeCursor:
        def execute(self, sql, params):
            captured.append((sql, params))

        def fetchall(self):
            return []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_conn = MagicMock()
    fake_conn.cursor.return_value = FakeCursor()
    fake_conn.__enter__ = lambda self: self
    fake_conn.__exit__ = lambda self, *a: False

    with (
        patch.object(repository._pool, "open"),
        patch.object(repository._pool, "connection") as mock_connection,
    ):
        mock_connection.return_value.__enter__.return_value = fake_conn
        repository._opened = True
        get_recent_edits(limit=42)

    assert captured
    sql, params = captured[0]
    assert sql.strip() == repository._SELECT_RECENT.strip()
    assert params == (42,)


def test_get_recent_edits_maps_operational_error_to_database_unavailable():
    with (
        patch.object(repository._pool, "open"),
        patch.object(repository._pool, "connection", side_effect=OperationalError("down")),
    ):
        repository._opened = True
        with pytest.raises(DatabaseUnavailable):
            get_recent_edits()
