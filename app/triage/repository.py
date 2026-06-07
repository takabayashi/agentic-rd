"""Postgres-backed repository for classified edits.

This is the data-source seam the web layer depends on (it replaces the Phase 2
`mock_data.load_edits`). The connection pool is constructed at import time but
opened lazily, so importing this module never connects to — or requires — a live
database. That keeps unit tests and CI DB-free while the real pool is used at
runtime.
"""

import os

from psycopg import OperationalError
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .models import EditView

DSN = os.getenv("DATABASE_URL", "postgresql://wiki:change-me@postgres:5432/wiki")

# Short timeouts so a missing/slow DB fails fast into a 503 rather than hanging a
# request. `check` validates a connection before handing it out, so the pool
# recovers automatically after Postgres is restarted. `open=False` defers the
# first connection attempt until a query actually runs.
_pool = ConnectionPool(
    DSN,
    min_size=1,
    max_size=5,
    open=False,
    timeout=3.0,
    check=ConnectionPool.check_connection,
    kwargs={"connect_timeout": 3},
)
_opened = False

_SELECT_RECENT = """
    SELECT rev_id, title, editor, comment, label, confidence,
           escalated, size_delta, uri, event_ts, classified_at
    FROM classified_edits
    ORDER BY event_ts DESC
    LIMIT %s
"""


class DatabaseUnavailable(Exception):
    """Raised when the database can't be reached. The web layer maps this to a
    503 warm-up response instead of crashing the request."""


def _ensure_open() -> None:
    """Open the pool on first use. `open(wait=False)` never blocks or raises if
    the DB is down — connections are established in the background."""

    global _opened
    if not _opened:
        _pool.open(wait=False)
        _opened = True


def get_recent_edits(limit: int = 200) -> list[EditView]:
    """Return the most recent classified edits as ``EditView`` objects.

    Raises ``DatabaseUnavailable`` on any connection failure so a cold start or
    a transient outage degrades gracefully (and recovers on the next request).
    """

    _ensure_open()
    try:
        with (
            _pool.connection(timeout=3.0) as conn,
            conn.cursor(row_factory=class_row(EditView)) as cur,
        ):
            cur.execute(_SELECT_RECENT, (limit,))
            return cur.fetchall()
    except (OperationalError, PoolTimeout) as exc:
        raise DatabaseUnavailable(str(exc)) from exc


def close_pool() -> None:
    """Close the pool on app shutdown (called from the FastAPI lifespan)."""

    global _opened
    if _opened:
        _pool.close()
        _opened = False
