"""Cross-layer schema guard.

The 11-field edit contract is maintained by hand in three languages: the
``EditView`` pydantic model (Python), the ``classified_edits`` table
(``db/init.sql``), and the Bloblang projection in the Connect pipeline. This
test ties the two we can introspect together — if someone adds a column or a
model field without the other, it fails — catching the most likely drift
without a live database.
"""

import re
from pathlib import Path

from triage.models import EditView
from triage.schema import classified_edits

_INIT_SQL = Path(__file__).resolve().parents[2] / "db" / "init.sql"


def _columns_from_init_sql() -> set[str]:
    """Parse the column names out of the CREATE TABLE classified_edits block."""

    text = _INIT_SQL.read_text()
    body = re.search(
        r"CREATE TABLE IF NOT EXISTS classified_edits\s*\((.*?)\n\);",
        text,
        re.DOTALL,
    )
    assert body, "could not locate the classified_edits CREATE TABLE block"

    columns: set[str] = set()
    for raw in body.group(1).splitlines():
        line = raw.strip()
        # Skip blanks, comments, and continuation lines (CHECK/constraint bodies
        # are indented further and don't start with an identifier + type).
        if not line or line.startswith("--") or line.startswith(("CHECK", "CONSTRAINT")):
            continue
        m = re.match(r"([a-z_]+)\s+[A-Z]", line)
        if m:
            columns.add(m.group(1))
    return columns


def test_editview_fields_match_classified_edits_columns():
    model_fields = set(EditView.model_fields.keys())
    sql_columns = _columns_from_init_sql()
    assert model_fields == sql_columns, (
        f"EditView fields and classified_edits columns drifted.\n"
        f"  only in model: {model_fields - sql_columns}\n"
        f"  only in SQL:   {sql_columns - model_fields}"
    )


def test_sqlalchemy_table_matches_init_sql():
    """The Alembic schema source (triage.schema) must agree with db/init.sql."""

    orm_columns = {c.name for c in classified_edits.columns}
    sql_columns = _columns_from_init_sql()
    assert orm_columns == sql_columns, (
        f"triage.schema and db/init.sql drifted.\n"
        f"  only in ORM: {orm_columns - sql_columns}\n"
        f"  only in SQL: {sql_columns - orm_columns}"
    )
