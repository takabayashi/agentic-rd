-- Schema for the Wikipedia Edit-Triage dashboard / pipeline sink.
--
-- `classified_edits` holds the *current* triage state of each edit. `rev_id`
-- is the natural primary key so the Connect pipeline (Phase 9) can UPSERT
-- (`INSERT ... ON CONFLICT (rev_id) DO UPDATE`): a cold-start or transient-LLM
-- failure that first lands a row as `unclear` is corrected in place by a later,
-- more confident pass — no duplicates, no PK collisions.
--
-- Run automatically by the postgres image's docker-entrypoint-initdb.d on first
-- init only (empty data dir). To re-run schema + seed: `docker compose down -v`.

CREATE TABLE IF NOT EXISTS classified_edits (
    rev_id        BIGINT PRIMARY KEY,                       -- Wikipedia rev ids exceed 32-bit
    title         TEXT             NOT NULL,
    editor        TEXT             NOT NULL,
    comment       TEXT             NOT NULL DEFAULT '',
    -- CHECK constraint (not a PG ENUM type): adding/renaming a label later is a
    -- one-line constraint change, no `ALTER TYPE`. Rejects out-of-enum labels.
    label         TEXT             NOT NULL
                  CHECK (label IN ('vandalism', 'substantive', 'trivia', 'unclear')),
    confidence    DOUBLE PRECISION NOT NULL
                  CHECK (confidence >= 0 AND confidence <= 1),
    escalated     BOOLEAN          NOT NULL DEFAULT FALSE,
    size_delta    INTEGER          NOT NULL DEFAULT 0,
    uri           TEXT             NOT NULL,
    event_ts      TIMESTAMPTZ      NOT NULL,                -- ISO string from Bloblang, never raw epoch
    -- Why this row got its label: 'classified' = the LLM decided; 'empty_diff' =
    -- the content gate skipped the model (no usable diff) and defaulted unclear.
    -- Lets the dashboard distinguish a model 'unclear' from a gated one.
    reason        TEXT             NOT NULL DEFAULT 'classified'
                  CHECK (reason IN ('classified', 'empty_diff')),
    classified_at TIMESTAMPTZ      NOT NULL DEFAULT now()
);

-- The dashboard reads the most recent edits first (then filters/sorts in-app),
-- so index the recency scan.
CREATE INDEX IF NOT EXISTS idx_classified_edits_event_ts
    ON classified_edits (event_ts DESC);
