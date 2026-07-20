# Spec 035 — Grounding Cost Attribution

**Status:** Draft (mini-spec). Follow-up to `033-ai-gateway-v2` / `034-multifield-provider-auth`.
**Trigger:** Pick up only after `feat/ai-gateway-v2` merges to `main`.
**Do NOT** change the `cost_logs` schema until this is implemented deliberately.

## Problem

`cost_logs.session_id` is declared as a hard foreign key to review sessions:

```sql
-- migrations/001_initial.sql
CREATE TABLE cost_logs (
    id TEXT PRIMARY KEY,
    review_id TEXT NOT NULL REFERENCES reviews(id),   -- renamed to session_id in 003
    ...
);
-- migrations/003_gateway.sql
ALTER TABLE cost_logs RENAME COLUMN review_id TO session_id;
```

So every logged LLM call must reference an existing `reviews` row.

The Citation Grounding Discriminator (`grounding/discriminator.py`) runs as a
post-review step that is **opt-in** (`--grounding-mode`) and, in the live test
path, can run without any review session at all. When `Gateway.chat` is called
for grounding and `session_id` is `None`/`""`, `log_call` attempts
`INSERT ... session_id=""` → `FOREIGN KEY constraint failed` → the exception
bubbles out of `chat`.

That was fixed for *availability* in `feat/ai-gateway-v2` commit `e2f73d1`
(T030): `Gateway.chat` now swallows cost-logging failures and still returns the
model response. But the **cost is silently never recorded** — grounding calls
do not appear in cost reports (`get_session_cost`, daily/per-review totals).

So the symptom is gone (calls don't fail) but the data gap remains: grounding
spend is invisible.

## Two paths (pick one when implementing)

### Option A — Make `session_id` nullable + drop the FK
- Alter `cost_logs`: `session_id TEXT` (nullable), remove `REFERENCES reviews(id)`.
- Grounding / non-review calls log with `session_id = NULL` (or omit it).
- Cost rollups that group by `session_id` still work for review calls; grounding
  shows up under "no session" / a null bucket.
- **Pros:** smallest schema change; no fake data; honest about unattributed cost.
- **Cons:** breaks the current guarantee that every cost is tied to a review;
  reporting must handle the null bucket. Any code assuming a non-null session
  needs updating.

### Option B — Generate a synthetic session for non-review flows
- When `Gateway.chat` is called without a real `session_id` (grounding, CLI
  `gateway test`, etc.), mint a synthetic session id (e.g. `grounding:<run_id>`
  or `cli-test:<timestamp>`) and log against that.
- Cost reports can attribute grounding spend to a recognizable synthetic session
  without polluting real review sessions.
- **Pros:** keeps the NOT NULL / FK invariant; grounding cost is attributable and
  queryable; no silent loss.
- **Cons:** requires a session-creation path that does NOT require a `reviews`
  row (the FK to `reviews` must still be relaxed or pointed at a `sessions` table
  that synthetic rows can join); slightly more moving parts.

## Open questions to resolve during implementation
- Keep the FK but point it at a new `sessions` table (review + synthetic rows),
  or drop it entirely (Option A)?
- Should grounding cost be rolled into the parent review's totals when a
  grounding run IS part of a review session? (Currently grounding runs after
  `run_review` returns, so it has no session even then.)
 - Migration safety: existing `cost_logs` rows have real `session_id`s — the
   alter must preserve them and only relax the constraint.
 - Whichever option is picked (A or B) must also correctly feed the **daily and
   session spend-LIMIT check**, not just the cost *report*. A grounding call
   that is invisible to the limit check could let someone exceed real spending
   caps unnoticed — the limit enforcement path must read the same cost rows the
   report reads.
 - Does 035 actually depend on 034 landing first? (Likely **no** — 035 is about
   the `cost_logs.session_id` foreign key and cost recording; 034 is about
   multi-field *provider* auth. They touch different layers. Confirm during
   planning; the dependency was probably listed in error.)


## Acceptance criteria (draft)
1. A grounding call (or any `Gateway.chat` without a review session) records its
   cost in `cost_logs` and is visible via `get_session_cost` / daily totals.
2. No `FOREIGN KEY constraint failed` / swallowed-log regression (covered by the
   existing `test_chat_survives_cost_logging_failure` + a new test asserting the
   row is actually written).
3. Existing review-cost reporting unchanged for review sessions.
4. mypy --strict, ruff, existing unit + integration suites green.

## Out of scope
- Multi-field provider auth (see `034`).
- Changing the privacy-tier cost model.
- Per-clause cost breakdowns (future enhancement).
