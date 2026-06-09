"""SQLAlchemy table definition for ``classified_edits``.

This is the schema source used by Alembic migrations (the migration creates the
table from this metadata). Runtime queries still use raw psycopg — this module
exists only so migrations and the schema-contract test have one Python-side
definition to agree on. It is kept in lockstep with ``db/init.sql`` (the
fresh-volume bootstrap) by ``tests/test_schema_contract.py``.
"""

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    text,
)

metadata = MetaData()

LABELS = ("vandalism", "substantive", "trivia", "unclear")

classified_edits = Table(
    "classified_edits",
    metadata,
    Column("rev_id", BigInteger, primary_key=True),
    Column("title", Text, nullable=False),
    Column("editor", Text, nullable=False),
    Column("comment", Text, nullable=False, server_default=text("''")),
    Column("label", Text, nullable=False),
    Column("confidence", Float, nullable=False),
    Column("escalated", Boolean, nullable=False, server_default=text("false")),
    Column("size_delta", Integer, nullable=False, server_default=text("0")),
    Column("uri", Text, nullable=False),
    Column("event_ts", DateTime(timezone=True), nullable=False),
    Column("classified_at", DateTime(timezone=True), nullable=False, server_default=text("now()")),
    CheckConstraint(
        "label IN ('vandalism', 'substantive', 'trivia', 'unclear')",
        name="classified_edits_label_check",
    ),
    CheckConstraint(
        "confidence >= 0 AND confidence <= 1",
        name="classified_edits_confidence_check",
    ),
    Index("idx_classified_edits_event_ts", text("event_ts DESC")),
)
