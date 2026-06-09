"""Alembic environment.

Reads the database URL from the app settings (DATABASE_URL) and normalizes it to
the psycopg-3 dialect (``postgresql+psycopg://``), since that's the driver the
app already ships. Online mode only — we always run against a live DB.
"""

from alembic import context
from sqlalchemy import create_engine
from triage.config import get_settings
from triage.schema import metadata

target_metadata = metadata


def _sync_url() -> str:
    url = get_settings().database_url
    # SQLAlchemy's bare postgresql:// dialect defaults to psycopg2 (not
    # installed); pin it to the psycopg-3 driver we already depend on.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_online() -> None:
    engine = create_engine(_sync_url(), pool_pre_ping=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
