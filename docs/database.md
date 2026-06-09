# Database

[← Back to README](../README.md)

Schema lives in [`db/init.sql`](../db/init.sql); sample rows in
[`db/seed.sql`](../db/seed.sql). Both are applied by the Postgres image's
init-entrypoint **only on first start** of an empty data volume — this is the
zero-tooling bootstrap so a fresh `docker compose up` always works. To re-apply
after editing them, recreate the volume:

```bash
docker compose down -v && docker compose up
```

Connect with `psql`:

```bash
docker compose exec postgres psql -U wiki -d wiki -c "SELECT rev_id, label, confidence FROM classified_edits ORDER BY confidence DESC;"
```

`classified_edits` columns: `rev_id` (BIGINT PK), `title`, `editor`, `comment`,
`label` (TEXT + CHECK enum `vandalism|substantive|trivia|unclear`), `confidence`
(0–1), `escalated`, `size_delta`, `uri`, `event_ts` (TIMESTAMPTZ),
`classified_at`.

`rev_id` is the primary key so the pipeline can UPSERT
(`ON CONFLICT (rev_id) DO UPDATE`): a row first classified `unclear` on a
cold-start/transient failure is corrected in place by a later, more confident
pass — no duplicates, no PK collisions. The `label` CHECK rejects any out-of-enum
value at the database boundary. DB credentials come from env only (`POSTGRES_*` /
`DATABASE_URL`); change the default password for any non-throwaway use.

The dashboard's empty state shows automatically whenever the table has no rows
(for example, on a fresh volume before the pipeline runs).

**Schema changes.** [`db/init.sql`](../db/init.sql) creates the table on first
Postgres boot (empty volume). A schema-contract test
([`app/tests/test_schema_contract.py`](../app/tests/test_schema_contract.py))
keeps `EditView` and `db/init.sql` in sync. Schema changes are applied by editing
`init.sql` and recreating the volume (`docker compose down -v`).
