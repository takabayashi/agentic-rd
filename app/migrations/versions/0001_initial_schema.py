"""initial classified_edits schema

Revision ID: 0001
Revises:
Create Date: 2026-06-08

Creates the table from the SQLAlchemy metadata in ``triage.schema``. Uses
``create_all(checkfirst=True)`` so it is a safe no-op when the table already
exists (e.g. a fresh volume already bootstrapped by db/init.sql) — Alembic then
simply records this as the baseline revision.
"""

from alembic import op
from triage.schema import classified_edits, metadata

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind(), tables=[classified_edits], checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(op.get_bind(), tables=[classified_edits], checkfirst=True)
