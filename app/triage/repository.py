"""Postgres-backed repository for classified edits.

This is the data-source seam the web layer depends on. The connection pool is
created lazily on first use (so importing this module never connects to — or
requires — a live database, keeping unit tests and CI DB-free), then reused.
Short timeouts + a per-checkout connection ``check`` mean a missing/slow DB
fails fast into a 503 and the pool self-heals after Postgres restarts.
"""

from psycopg import OperationalError
from psycopg.rows import class_row
from psycopg_pool import ConnectionPool, PoolTimeout

from .config import get_settings
from .models import EditView

_SELECT_RECENT = """
    SELECT rev_id, title, editor, comment, label, confidence,
           escalated, size_delta, uri, event_ts, reason, classified_at
    FROM classified_edits
    ORDER BY event_ts DESC
    LIMIT %s
"""

# Module-level pool handle, built on first use via `_get_pool()`.
_pool: ConnectionPool | None = None


class DatabaseUnavailable(Exception):
    """Raised when the database can't be reached. The web layer maps this to a
    503 warm-up response instead of crashing the request."""


def _get_pool() -> ConnectionPool:
    """Build (once) and return the connection pool.

    ``open=True`` here is safe because the pool opens connections in the
    background and never blocks/raises if the DB is down. Subsequent calls reuse
    the same pool.
    """

    global _pool
    if _pool is None:
        s = get_settings()
        _pool = ConnectionPool(
            s.database_url,
            min_size=s.pool_min_size,
            max_size=s.pool_max_size,
            open=True,
            timeout=s.db_timeout_seconds,
            check=ConnectionPool.check_connection,
            kwargs={"connect_timeout": s.db_connect_timeout},
        )
    return _pool


def get_recent_edits(limit: int | None = None) -> list[EditView]:
    """Return the most recent classified edits as ``EditView`` objects.

    Raises ``DatabaseUnavailable`` on any connection failure so a cold start or
    a transient outage degrades gracefully (and recovers on the next request).
    """

    if limit is None:
        limit = get_settings().recent_window_limit
    pool = _get_pool()
    try:
        with (
            pool.connection(timeout=get_settings().db_timeout_seconds) as conn,
            conn.cursor(row_factory=class_row(EditView)) as cur,
        ):
            cur.execute(_SELECT_RECENT, (limit,))
            return cur.fetchall()
    except (OperationalError, PoolTimeout) as exc:
        raise DatabaseUnavailable(str(exc)) from exc


def check_ready() -> bool:
    """Return True if the database is reachable right now (for /readyz).

    Never raises: a down/warming DB simply returns False.
    """

    try:
        pool = _get_pool()
        with pool.connection(timeout=get_settings().db_timeout_seconds) as conn:
            conn.execute("SELECT 1")
        return True
    except (OperationalError, PoolTimeout):
        return False


def close_pool() -> None:
    """Close the pool on app shutdown (called from the FastAPI lifespan)."""

    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
