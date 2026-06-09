-- Seed rows so the dashboard has data before the ingest pipeline exists
-- (Phases 4-9). Mirrors the Phase 2 fixture in app/mock_data.py. Idempotent via
-- ON CONFLICT so re-running (or a later real UPSERT) is safe.

INSERT INTO classified_edits
    (rev_id, title, editor, comment, label, confidence, escalated, size_delta, uri, event_ts, reason, classified_at)
VALUES
    (1300000001, 'Python (programming language)', 'HelpfulEditor',
     'Expanded the section on the standard library with sourced examples.',
     'substantive', 0.94, false, 1842,
     'https://en.wikipedia.org/w/index.php?diff=1300000001',
     '2026-06-07T12:00:00Z', 'classified', '2026-06-07T12:00:00Z'),
    (1300000002, 'List of common misconceptions', '192.0.2.51',
     'POOP POOP POOP haha you cant stop me',
     'vandalism', 0.97, false, -512,
     'https://en.wikipedia.org/w/index.php?diff=1300000002',
     '2026-06-07T12:00:00Z', 'classified', '2026-06-07T12:00:00Z'),
    (1300000003, 'Cricket World Cup', 'StatsBotHelper',
     'Fixed a typo in the 1996 final attendance figure.',
     'trivia', 0.81, false, 3,
     'https://en.wikipedia.org/w/index.php?diff=1300000003',
     '2026-06-07T12:00:00Z', 'classified', '2026-06-07T12:00:00Z'),
    (1300000004, 'Quantum entanglement', '203.0.113.7',
     'rewrote intro',
     'unclear', 0.41, true, 220,
     'https://en.wikipedia.org/w/index.php?diff=1300000004',
     '2026-06-07T12:00:00Z', 'classified', '2026-06-07T12:00:00Z'),
    (1300000005, 'Eiffel Tower', 'CuriousNewbie',
     'Updated the visitor count for 2025 and added a citation.',
     'substantive', 0.62, true, 95,
     'https://en.wikipedia.org/w/index.php?diff=1300000005',
     '2026-06-07T12:00:00Z', 'classified', '2026-06-07T12:00:00Z'),
    -- Demonstrates the content gate: an edit with no usable diff was labelled
    -- unclear *without* a model call (reason=empty_diff, confidence 0).
    (1300000006, 'Banana', '198.51.100.23',
     '',
     'unclear', 0.0, false, 2,
     'https://en.wikipedia.org/w/index.php?diff=1300000006',
     '2026-06-07T12:00:00Z', 'empty_diff', '2026-06-07T12:00:00Z')
ON CONFLICT (rev_id) DO NOTHING;
