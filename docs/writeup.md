# Design notes: tradeoffs, surprises, and where this breaks

This is the "why" behind the build. I wrote it as a personal project to get
hands-on with Redpanda Connect and a staged, multi-step local-LLM pipeline, so
the notes below are honest about what I chose, what I'd change, and where the
design falls over if you actually pushed traffic through it. For what the system
does and how to run it, see the [README](../README.md).

## Tradeoffs

### One LLM call vs. the confidence-escalation loop

I built the loop. Every surviving edit gets a cheap first pass over the diff plus
metadata; only the ambiguous ones (`confidence < CONFIDENCE_THRESHOLD`, default
`0.7`, or `label == "unclear"`) get a second, more rigorous pass with a per-label
rubric, the editor identity, and the first pass's answer for self-critique.
Confident rows skip the second model call entirely.

The reason it's worth two passes here is that the second pass adds *judgment*, not
new facts: both passes read the same fetched diff, so escalation is re-reasoning,
not re-fetching. `CONFIDENCE_THRESHOLD` is the cost lever, and it behaves the way
you'd expect: lower it and fewer edits escalate, raise it and more do. That makes
the accuracy/cost trade visible and tunable instead of baked in.

I'd flip to a single call if the diff weren't already in hand for pass one (then a
second pass would just be a more expensive guess over the same metadata), or if a
one-shot prompt hit whatever accuracy bar the use case needed. The loop earns its
keep only because pass one has real evidence to reason over and the threshold lets
me spend the second call selectively.

### Connect as the sink vs. an app-side consumer writing Postgres

I let Connect write Postgres directly. The classify stage ends in a `broker`
`fan_out` to three places: the `wiki.edits.classified` topic, a `sql_raw` UPSERT
into `classified_edits`, and the `model.audit` topic. No extra consumer service to
run, deploy, or monitor — the pipeline config is the whole story.

The honest caveat is the `fan_out` retry semantics: if any one output fails, the
message is retried to *all* outputs, so a transient Postgres blip can re-produce to
Kafka. That's only safe because the classified topic is compacted by `rev_id` and
the SQL write is an idempotent UPSERT, so duplicates converge to one correct row
rather than piling up. I also wrapped just the SQL output in `retry` so a Postgres
outage is retried instead of killing the batch.

I'd flip to an app-side consumer the moment I needed per-sink isolation — separate
retry/backpressure policies for Kafka vs. Postgres, or enrichment/validation in
real code before the write. Connect-as-sink trades that isolation for one less
moving part, which is the right call at this size and the wrong one once the write
path needs its own logic.

### Dedup via Postgres UPSERT vs. an in-pipeline cache

The only dedup in the system is the `rev_id` primary key plus
`ON CONFLICT (rev_id) DO UPDATE`, backed by compacted topics keyed on `rev_id`.
There's deliberately no `cache_resources`/`dedupe` step in Connect. On an SSE
firehose this is enough: the same `rev_id` almost never arrives twice, and the rare
reconnect replay just upserts the same row.

The thing to be clear about is what this does and doesn't buy. It guarantees the
*stored* row is correct and unique. It does **not** stop wasted work: under
at-least-once Kafka delivery, a consumer-group rebalance, or a replay after a prompt
change, the same edit can get re-classified — two model calls — even though the row
converges. That's fine on a stream that rarely repeats; it's wasteful on anything
that does.

So I'd add a real dedup step (a seen-key cache, or tracking processed offsets) the
moment the source changed shape — a poll-based source like Hacker News or GitHub
that refetches the same ids every poll would re-run the LLM on everything it already
saw. There the cache pays for itself immediately by skipping inference, and the
UPSERT stays as the durable backstop rather than the only line of defense.

## Surprises

A few things only showed up once I ran it against the live feed:

- **A smaller model was confidently wrong.** `qwen2.5:1.5b` labeled roughly 85% of
  edits `vandalism` at 0.96–1.00 confidence, including obviously good edits. Because
  the errors were *high* confidence, the escalation pass (which only triggers on
  *low* confidence) couldn't catch them. The whole self-correction story quietly
  depends on the model being uncertain when it's wrong, which a too-small model
  isn't. I went back to `llama3.2`.
- **A Bloblang `mapping` rebuilds `root` from scratch.** A trailing
  `- mapping: root.escalated = true` wiped every other field and left rows as
  `{"escalated": true}`. Inside a `branch`'s `result_map` the rule inverts (partial
  assignments graft back onto the record), so that's where `escalated` has to be
  set. Easy to get backwards, and the failure is silent until you look at the data.
- **An unreachable model produced null comparisons, not errors at the call site.**
  When Ollama was down, Connect skipped the branch's `result_map`, so records reached
  the escalation `switch` with no `confidence` field and crashed it on
  `null < threshold` — 328 `cannot compare types null` errors and zero labeled rows.
  The fix was a fail-safe default to `unclear`/`0` so a missing classification is
  still a valid record.
- **JSON numbers are float64.** `rev_id.string()` rendered `1.35e+09` and broke the
  diff URLs until I cast it with `.int64()`. Wikipedia revision ids are big enough
  to hit scientific notation, which is not where you expect to lose an afternoon.

## Where this breaks in production

I built this to learn the tools on a laptop, not to run at Wikipedia's real edit
volume. The places it would break, roughly in order of how soon you'd hit them:

**LLM throughput and cost — the first wall.** One Ollama process is a single
inference queue; on CPU that's seconds per call, and an escalated edit pays for two.
`connect-classify` can be scaled to multiple replicas (the metrics port is already
target-only so replicas don't collide), but each replica still needs its own
model-resident Ollama with enough RAM or a GPU, so the bottleneck just moves to GPU
capacity and cost. Against a ~50 edits/sec firehose this falls behind quickly.

**An LLM is probably the wrong tool here at scale.** For a four-way label, a cheap
classifier would be orders of magnitude faster and more consistent: a small
fine-tuned text classifier, or even decent heuristics on diff size, editor
anonymity, reverts, and keyword signals. The sensible production shape is a fast
model on every edit and the LLM (or a fine-tuned model) reserved for the genuinely
ambiguous tail. Right now I run the most expensive option on the widest set; the
content gate trims the obvious no-ops but not the core cost. Fine-tuning on labeled
Wikipedia edits would likely beat prompt-only `llama3.2` on both accuracy and
cost-per-call — at the price of a labeling, training, and eval pipeline this project
doesn't have. That's the real path forward, and it's out of scope here on purpose.

**It isn't built to scale, full stop.** Single-node Redpanda
(`--mode=dev-container`, memory-capped) with no replication. One Postgres, no
replicas; the dashboard reads a recent window and filters/sorts in the app, which
won't hold as the table grows (that wants SQL-side filtering, indexes, and real
pagination). Everything is one replica on one host under `docker compose` — no
orchestration, autoscaling, or cross-stage backpressure tuning.

**Dedup needs an actual strategy.** As above, today's `rev_id` UPSERT converges the
row but doesn't prevent re-classifying the same edit under replays, rebalances, or a
poll-based source. A production build wants an idempotency/seen-key check *before*
inference so you don't pay to re-label what you've already labeled.

**The audit log doesn't scale as-is.** `model.audit` (full prompts plus both passes'
raw responses) is great for visualizing *why* a label happened while developing, and
surfacing it in the DB would help inspection. At real volume it's a lot of data, it
embeds attacker-controlled title/comment/diff text, and storage, retention, and PII
handling all add up. In production it would be sampled, short-retention,
access-controlled, and almost certainly not mirrored into the serving database.

**Other edges I know about.** The Wikipedia REST compare API returns 429s under
sustained load; the enrich stage fails closed to an empty diff, so classification
silently degrades to metadata-only. There's no auth on the dashboard — it assumes a
localhost-only posture. And the containerized Ollama crashes during inference on
arm64 Colima (a virtualization/cgo issue), so the Mac path is host-native Ollama
pointed at via `OLLAMA_ADDRESS`.
