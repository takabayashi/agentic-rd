"""Integration test: the repository against a real Postgres.

Spins up a throwaway Postgres with testcontainers, applies ``db/init.sql``,
inserts a row, and exercises ``get_recent_edits`` / ``check_ready`` end-to-end
(real psycopg, real SQL, real pool). Skipped automatically when Docker isn't
available so unit CI stays infra-free; run it where Docker is present (locally
or a Docker-enabled CI job).
"""

from pathlib import Path

import psycopg
import pytest

testcontainers_postgres = pytest.importorskip("testcontainers.postgres")
from testcontainers.postgres import PostgresContainer  # noqa: E402

_INIT_SQL = Path(__file__).resolve().parents[2] / "db" / "init.sql"


@pytest.fixture(scope="module")
def pg_url():
    """Start Postgres; skip the module if Docker isn't reachable."""

    try:
        container = PostgresContainer("postgres:16.14", driver="psycopg")
        container.start()
    except Exception as exc:  # docker missing / not running
        pytest.skip(f"Docker/testcontainers unavailable: {exc}")
    try:
        # testcontainers returns a psycopg URL; the app expects bare postgresql://.
        url = container.get_connection_url().replace("postgresql+psycopg://", "postgresql://")
        yield url
    finally:
        container.stop()


@pytest.fixture
def repo(pg_url, monkeypatch):
    """Point the repository at the container and reset its cached pool/settings."""

    from triage import config, repository

    monkeypatch.setenv("DATABASE_URL", pg_url)
    config.get_settings.cache_clear()
    repository.close_pool()

    with psycopg.connect(pg_url) as conn:
        conn.execute(_INIT_SQL.read_text())
        conn.commit()

    yield repository

    repository.close_pool()
    config.get_settings.cache_clear()


def _insert_sample(url: str) -> None:
    with psycopg.connect(url) as conn:
        conn.execute(
            """
            INSERT INTO classified_edits
              (rev_id, title, editor, comment, label, confidence, escalated,
               size_delta, uri, event_ts, classified_at)
            VALUES (1, 'T', 'E', 'c', 'vandalism', 0.9, false, 5,
                    'https://en.wikipedia.org/w/index.php?diff=1', now(), now())
            ON CONFLICT (rev_id) DO NOTHING
            """
        )
        conn.commit()


def test_check_ready_true_against_live_db(repo, pg_url):
    assert repo.check_ready() is True


def test_get_recent_edits_reads_real_rows(repo, pg_url):
    _insert_sample(pg_url)
    edits = repo.get_recent_edits()
    assert len(edits) == 1
    assert edits[0].rev_id == 1
    assert edits[0].label.value == "vandalism"
