# Grounding accuracy harness — design (scoring citation grounding honestly)

**Scope:** a grounding-accuracy mode added to the existing measurement script
(`scripts/measure_slm_slots.py`), the labelling fix in `src/openreview_cli/grounding/corruption.py`,
and the tests/receipts that come with them. **No production scoring code is changed.**

**Base:** worktree `035-post-measurement-cleanup`, branch `feat/035-post-measurement-cleanup`
at `c49ee21`.

**Status:** design only — nothing implemented. Master plan §6 (Phase 3) is the source; this doc is
the per-item sub-plan §0 promises. Decisions 1 and 14 and warning W12 of
`draft/measurement-decisions-2026-09-29.md` are the evidence record.

**Deliverable:** a runnable mode, honest labels, one guard, a real confusion matrix, a JSON receipt
plus a markdown report, and the tests in §8.

Every `file:line` below was verified against the worktree sources on 2026-09-30; §10 lists what was
taken from the master plan rather than re-read, and what could not be verified.

---

## 1. Why this is needed (the evidence, with proofs)

1. **Strict mode removes the failure before anyone can see it.** `precheck review` defaults
   `--grounding-mode` to `strict` (`app.py:1378-1382`, `runner.py:169`). Strict filtering drops
   ungrounded claims before the report, so the surviving counts cannot show a miss. The measured
   run: **7 claims assessed, 7 grounded, 0 ungrounded** — and nothing was removed
   (`docs/benchmarks/results/slot-measurement.md:33-36`). We cannot tell whether grounding works or
   is asleep.
2. **The existing metrics function cannot expose it.** `compute_cg_metrics` scores *structural*
   CP/CR/CL over grounded verdicts only, and returns `1.0` for **everything** when nothing is
   grounded — `src/openreview_cli/grounding/metrics.py:100-105`:

   ```python
   if n_grounded == 0:
       return CGMetrics(citation_precision=1.0, citation_relevance=1.0, citation_locality=1.0)
   ```

   A grounding that rejects everything therefore scores **perfect**. That is the exact failure mode
   this harness exists to expose, and it is why the harness must not use that function as its
   signal.
3. **It is production code and stays untouched.** `compute_cg_metrics` is consumed at
   `grounding/discriminator.py:219` (`ground_report`) and exported at
   `grounding/__init__.py:14,40`. **Its behaviour must not change.** The harness measures around it,
   never through it (§4, §4.3).
4. **No harness exists, and the one labelled fixture is unusable.** `tests/fixtures/grounding/
   seeded_claims.json` carries 20 labelled claims but **no source clause text and no source
   document**, and has **zero consumers** (record W7). It is deleted in Phase 1 (master plan T1.7);
   the harness does not need it, because `ground_claim(claim_text, cited_clause_id, clause_text)`
   takes the clause text directly (`grounding/discriminator.py:65-70`).
5. **The corruption generators cannot supply correct labels as written** (record W12):
   `clause_swap` (`corruption.py:18-36`) and `anachronism` (`:84-98`) both corrupt by
   `claim.replace(clause_id, …)`, which **no-ops on prose claims** (`replace` returns the original
   when the id does not appear) — so a no-op comes back labelled `ungrounded`, a mislabel.
   `category_swap` (`:39-56`) keeps the clause text unchanged, so the claim stays supported.
   `hallucination` (`:59-81`) draws from 10 fixed sentences, one of which (index 4, line 73:
   "shall indemnify and hold harmless") is genuinely supported by an indemnity clause.

---

## 2. The label scheme

One label = `(claim_text, cited_clause_id, clause_text, expected)` where `expected ∈ {supported,
unsupported}`. The clause text and id come from the same source unit, so there is no plumbing
between claim and source.

### 2.1 Positives — a verbatim sentence from the cited clause

For a source unit `u = (id, text)`:

- sentences are extracted with the repo's **own** sentence boundary detector,
  `nupunkt_detect_boundaries(text)` (`parsing/clause_detector.py:19-30`, wrapping `nupunkt`'s
  `sent_spans`), which returns `(start, end)` spans sliceable back to the verbatim sentence —
  verified in the worktree venv: `[(0, 65), (65, 122)]` for a two-sentence paragraph. No new
  dependency.
- the positive is `claim_text = text[start:end].strip()`, `cited_clause_id = id`,
  `clause_text = text`. It is supported **by construction**.

**State plainly, in the report and in code comments, that this is a weaker, easier positive set than
a human-labelled one**: a verbatim sentence from the clause is trivially grounded
(record R5, master plan §9). The meaningful signal is the **negative** arm — whether a bad claim is
caught. Never quote a "real-world false-positive rate" from this harness.

Selection rules (deterministic, no RNG): a sentence qualifies when it has ≥ 8 words and ≥ 40
characters, and the unit qualifies when it yields ≥ 1 qualifying sentence; the harness takes one
qualifying sentence per unit (the first), so the positive and the negative arms are paired per
clause.

### 2.2 Negatives — two generators, both through the guard (§3)

| Generator | Produces | Why it is a genuine negative |
|---|---|---|
| `unsupported_claim(clause_a, clause_b)` → claim is a **verbatim sentence from `clause_b`**, asserted against `clause_a` | cross-clause | The claim text is a real sentence, but from a *different* clause; no string surgery, so no silent no-op. It is the honest replacement for `clause_swap`'s broken `claim.replace`. |
| `hallucination(claim)` (`grounding/corruption.py:59-81`), unchanged | fabricated sentence | Draws from 10 fixed fabrications with no support in the document — **except** where a fabrication happens to be supported by this clause (e.g. index 4 against an indemnity clause). The guard drops those. |

`unsupported_claim(clause_a, clause_b)` is added **to `grounding/corruption.py`** (master plan
T3.1), additive only, next to the existing generators:

- `clause_a`/`clause_b` are the `(id, text)` units of §2.1 (typed as such, not as `Clause` — the
  harness's units are plain text, and `ground_claim` builds its own `Clause` internally,
  `discriminator.py:86-97`);
- it picks the first qualifying sentence of `clause_b` (same rule as §2.1), asserts it against
  `clause_a.id` / `clause_a.text`;
- it returns the claim text, or `None` when `clause_b` has no qualifying sentence — the caller
  simply skips that pair (no silent empty claim).

### 2.3 Excluded, with reasons

| Generator | Disposition | Reason |
|---|---|---|
| `category_swap` (`corruption.py:39-56`) | **excluded** | It replaces a playbook *category label* and keeps the clause text unchanged, so the claim stays supported by its clause. It is a classification/comparison case, **not** a support case. It cannot produce a grounding negative at all. |
| `anachronism` (`corruption.py:84-98`) | **excluded** | It rewrites the clause-id reference inside the claim's *text*: that is **citation validity**, not claim support. It also no-ops on prose claims (`claim.replace`, W12). If citation validity is ever scored, it gets its own harness with its own contract. |
| `clause_swap` (`corruption.py:18-36`) | **not used** | Same `claim.replace` no-op class as `anachronism`; superseded by `unsupported_claim`, which changes the *clause text the claim is asserted against* instead of the claim string. Left in the module unchanged (its existing unit tests still pass). |

---

## 3. The mandatory guard

Every generated negative is checked **before it enters the label set**:

```
normalize(s) = " ".join(s.split()).casefold()
KEEP   iff  normalize(negative_claim) not in normalize(cited_clause_text)
DROP   otherwise, incrementing dropped_by_guard[generator]
```

- This is a substring test on the exact claim the discriminator will see, against the exact clause
  text it will be given. If the claim appears verbatim in the cited clause, the claim is *supported*
  and the label would be wrong.
- A mislabelled negative is **dropped, never kept**: the harness must not measure its own labelling
  errors (record W12's closing line).
- `dropped_by_guard` is recorded **per generator** and printed in the report and in the receipt.
  The report must state the number even when it is zero.
- The no-op case is caught by the same guard for free: a generator that returns the input unchanged
  produces a claim that *is* (part of) the clause text, so `normalize(claim) in
  normalize(clause_text)` and it is dropped.

Unit tests for the guard are in §8.1.

---

## 4. The metrics — a real confusion matrix, and nothing else

### 4.1 The matrix

One row per call to `CitationGroundingDiscriminator.ground_claim(claim_text, cited_clause_id,
clause_text)` (`grounding/discriminator.py:65-123`), which returns
`(GroundingVerdict, provenances, confidence)`. A verdict of `UNCERTAIN` (including a gateway
failure, `:113-115`, or an unparseable reply, `:117-120`) is **its own column** — it is neither
"caught" nor "accepted", and folding it into either would hide a real behaviour.

| truth \ verdict | `grounded` | `ungrounded` | `uncertain` |
|---|---|---|---|
| **positive** (verbatim clause sentence) | `good_accepted` | **`good_rejected`** | `good_uncertain` |
| **negative** (kept by the guard) | **`bad_missed`** | **`bad_caught`** | `bad_uncertain` |

Reported quantities:

| Quantity | Definition | Degenerate case |
|---|---|---|
| `positives` (P) | labels with `expected = supported` | — |
| `negatives_kept` (N) | labels with `expected = unsupported` that survived §3 | `0` allowed |
| `negatives_dropped_guard` | generated − kept, per generator | `0` allowed |
| **bad claims caught** | `bad_caught`; rate `caught_rate = bad_caught / N` | `caught_rate is None` when `N == 0` — **never 1.0** |
| `bad_missed` | negatives the grounding accepted | — |
| **good claims wrongly rejected** | `good_rejected`; rate `false_reject_rate = good_rejected / P` | `None` when `P == 0` |
| `good_uncertain`, `bad_uncertain` | counts only (no rate) | — |
| **per-call latency** | seconds around each `ground_claim` call: `calls`, `mean`, `median`, `p95`, `max` | — |

`caught_rate` and `false_reject_rate` are always reported **together** and are never collapsed into a
single score: a grounding that rejects everything has `caught_rate = 1.0` *and*
`false_reject_rate = 1.0`, and the second number is what makes it a failure. That pairing is the
whole point of a confusion matrix here.

### 4.2 The degenerate cases (which is what the arithmetic test pins)

- **All negatives drained by the guard** (`N == 0`): `bad_caught == 0` and `caught_rate is None`.
  The harness must **not** emit `1.0`, because there is nothing to catch; the receipt records
  `negatives_dropped_guard` so a reader can see why. This `N == 0` case is pinned by master plan
  T3.3 and §8.2. *(The separate case where the grounding rejects every claim is pinned by the next
  bullet, because under the `bad_caught` definition a reject-everything grounding legitimately
  catches 100% of negatives — what exposes it is `false_reject_rate == 1.0`.)*
- **The discriminator rejects everything** (`grounded` for no claim): `bad_caught == N` and
  `good_rejected == P`. Pinned as the mirror control, so the harness cannot be read as rewarding
  it.
- **Contrast test (documents the reason for not using `compute_cg_metrics`):** feeding that same
  reject-everything run into `compute_cg_metrics` yields `1.0 / 1.0 / 1.0`
  (`grounding/metrics.py:100-105`) — the test asserts the contrast so the structural function is
  never re-adopted as the signal.

### 4.3 What is deliberately not a signal

- **No `compute_cg_metrics` call, and no CP/CR/CL in the receipt.** It scores structural citation
  shape over grounded verdicts only and is blind to a rejection (master plan T3.2, §12 ponytail
  item). The harness must not even import it — asserted by a test (§8.2).
- **No aggregate/weighted single score.** Two rates and a latency table, all with their
  denominators visible.

---

## 5. Where it runs and how (extend, do not fork)

`scripts/measure_slm_slots.py` already owns everything this needs and is extended in place:

| Reused thing | Where it is today |
|---|---|
| slot override via `OPENREVIEW_GATEWAY__MODELS__*__PRIMARY` | `_configure_slots` `:45-48` |
| read the configured slots instead | `_configured_slots` `:51-58` |
| git sha for the receipt | `_git_sha` `:41-42` |
| `init_database(...)` before any gateway call (the `no such table: cost_logs` bug, record §1.6) | `:149-152` |
| markdown summary helper | `_markdown` `:85-105` |
| JSON receipt write | `:240-241`, `:224-239` |
| per-item loop that records `seconds` and an `error` per entry | `:172-221` |

New CLI surface (all default-off, so today's invocations are unchanged):

```
--grounding-accuracy           run the grounding-accuracy mode instead of the review mode
--arm {local,cloud,configured}  local = ollama/granite4:3b; cloud = the configured OpenRouter slot;
                                configured = whatever config.yml has for all three slots
--limit N                      max source units to label (default 20; the smoke run uses 20)
--corpus-dir PATH              default data/legalbenchrag/corpus/cuad
--out PATH                     JSON receipt (required, as today)
```

**Corpus and the source-unit rule.** The corpus is `data/legalbenchrag/corpus/cuad/*.txt` — 462
plain-text contracts, verified present in the parent checkout at
`/home/mohamed/lab/openreview/data/legalbenchrag/corpus/cuad/` (the directory also holds
`contractnli`, `maud`, `privacy_qa`; the harness targets **`cuad` only**). The files are blank-line
separated prose/numbered clauses (verified by reading
`2ThemartComInc_…_Co-Branding Agreement_ Agency Agreement.txt`). A **source unit** is a
blank-line-separated paragraph with ≥ 2 sentences and ≥ 200 characters; its id is harness-local
(`"c%03d" % index`) — the id only has to be stable and distinct, because `ground_claim` constructs
the `Clause` from the arguments itself (`discriminator.py:86-97`). The unit id is **not** the
product's clause numbering, and the report says so.

**Graceful skip when the corpus is absent.** `data/` is gitignored (record R6), so it is absent in
CI and in a fresh worktree (confirmed in this worktree). When `--corpus-dir` does not exist or
contains no `*.txt`: print `[grounding-accuracy] corpus absent at {path} — skipping.`, write a
receipt with `"skipped": true` and the corpus path, and **exit 0**. The mode must never fail CI for
a missing gitignored directory.

**The call.** Per label, construct one discriminator and call
`discriminator.ground_claim(claim_text, cited_clause_id, clause_text)`
(`grounding/discriminator.py:65`), timing with `time.perf_counter()` around it. The discriminator's
own constructor needs an audit directory and a `Gateway`; the harness passes a gateway built from
the arm's config and a `tempfile.mkdtemp()` audit dir (the existing default) so nothing is persisted
beyond the receipt. Zero-length or empty claims are never sent (`:81-83` returns `UNGROUNDED`
without a call) — the §2 selection rules already exclude them.

---

## 6. Arms, sample size, and the receipt

**Two arms, the same label set:**

- **local** — `ollama/granite4:3b`, the shipped default for all three text slots after Phase 1
  (decisions 12 / master plan §2).
- **cloud** — the configured OpenRouter slot (needs the key; record W10's spend-limit block was
  lifted). Local and cloud run the **same** labelled pairs (the label set is deterministic), so the
  comparison is paired.

**Sample size** is `--limit` units × (1 positive + up to 2 negatives each) minus guard drops; the
report states the actual counts, not the requested limit.

**Outputs**, matching the repo's benchmark convention (`docs/benchmarks/results/` already holds
`slot-measurement.json` + `slot-measurement.md`):

- `docs/benchmarks/results/grounding-accuracy-<arm>.json` — the receipt
  (`<arm>` ∈ `local`, `cloud`), written by the existing `--out` mechanism (`:240-241`);
- `docs/benchmarks/results/grounding-accuracy.md` — the markdown report, written by hand from the
  receipts in Phase 4 (the existing report file is hand-assembled the same way).

**Receipt fields:** `arm`, `model_ids` (per slot: `extraction` / `reasoning` / `grounding`),
`slots`, `corpus_dir`, `corpus_files_scanned`, `limit`, `skipped`, `git_sha`, `measured_at_utc`,
`positives`, `negatives_kept`, `negatives_dropped_guard` (total **and** per generator),
`good_accepted`, `good_rejected`, `good_uncertain`, `bad_caught`, `bad_missed`, `bad_uncertain`,
`caught_rate`, `false_reject_rate`, latency (`calls`, `mean`, `median`, `p95`, `max`), and a
`caveats` list. Per-label rows are kept in the receipt (claim text, unit id, expected, verdict,
confidence, seconds) so a reader can audit any single number.

**Caveats the report must state in its own prose:**

1. the sample size (units, positives, kept negatives, dropped negatives) and that it is a smoke
   measurement, not a benchmark;
2. the exact model IDs, per slot;
3. that **positives are verbatim clause sentences** and therefore an easier set than a
   human-labelled one — the negative arm is the signal, and no real-world false-positive rate may be
   quoted from this;
4. the number of negatives the guard dropped, per generator, and what that means;
5. that clause ids are harness-local units, not the product's clause numbering;
6. that the corpus is gitignored, so CI runs this mode only as the skip path.

---

## 7. Files

- Modify: `src/openreview_cli/grounding/corruption.py` — add `unsupported_claim(clause_a, clause_b)`
  (additive; existing generators and their tests untouched).
- Modify: `scripts/measure_slm_slots.py` — the `--grounding-accuracy` mode, the guard, the matrix,
  the receipt; reuse `_configure_slots`, `_configured_slots`, `_git_sha`, `_markdown`,
  `init_database`, the JSON write.
- Create: `tests/unit/test_grounding_harness.py` (metric arithmetic + guard + skip).
- Create: `tests/unit/test_grounding_harness_e2e.py` (offline, gateway stubbed).
- Modify: `tests/unit/test_grounding_corruption.py` — the `unsupported_claim` and guard cases.
- Create: `docs/benchmarks/results/grounding-accuracy-{local,cloud}.json`,
  `docs/benchmarks/results/grounding-accuracy.md` (Phase 4, from real runs).
- **Not touched:** `src/openreview_cli/grounding/metrics.py`, `grounding/discriminator.py`,
  `grounding/prompts.py`.

---

## 8. Tests and acceptance criteria

### 8.1 `tests/unit/test_grounding_corruption.py` (offline, fast)

1. `unsupported_claim(a, b)` returns a sentence that appears verbatim in `b.text` and **not** in
   `a.text` (the pair is chosen so the guard keeps it), and returns `None` for a `b` with no
   qualifying sentence.
2. The guard rejects a **no-op** corruption: feed a "negative" equal to the original claim, assert
   it is dropped and counted.
3. The guard rejects `hallucination`'s index-4 fabrication ("shall indemnify and hold harmless",
   `corruption.py:73`) against an indemnity clause, and keeps it against a non-indemnity clause.
4. `category_swap` is asserted to leave the claim supported (clause text unchanged) — documenting
   *why* it is excluded, so the exclusion cannot silently regress.

### 8.2 `tests/unit/test_grounding_harness.py` (offline, fast)

The metric function is imported as a pure helper (no gateway, no corpus) and fed hand-built verdict
lists:

1. **Arithmetic is exact on a hand-built matrix.** A 4-positive / 3-negative matrix with known
   verdicts yields the exact `good_accepted`/`good_rejected`/`good_uncertain`/`bad_caught`/
   `bad_missed`/`bad_uncertain` counts, `caught_rate` and `false_reject_rate`.
2. **All-rejected (guard drained the negative arm): scores zero caught.** Zero kept negatives →
   `bad_caught == 0`, `caught_rate is None` (never `1.0`), `negatives_dropped_guard` recorded.
3. **Mirror control: a reject-everything grounding cannot look good.** Every claim `UNGROUNDED` →
   `bad_caught == N` **and** `good_rejected == P`, `false_reject_rate == 1.0`.
4. **Contrast (the reason for §4.3):** that same reject-everything verdict list through
   `compute_cg_metrics(...)` returns `1.0 / 1.0 / 1.0` — asserted with a comment naming
   `grounding/metrics.py:100-105`, so the contrast is a *pinned fact* and not folklore.
5. **`compute_cg_metrics` is not the harness's signal.** Assert the harness module does not import
   it (a source-level check on the mode's import set), and that no CP/CR/CL key appears in the
   receipt.
6. **Latency aggregation**: `mean`/`median`/`p95`/`max` over a known list of per-call seconds.
7. **Uncertain is its own column**: an all-`UNCERTAIN` run yields zero caught, zero false rejects,
   and non-zero `*_uncertain` counts.

### 8.3 `tests/unit/test_grounding_harness_e2e.py` (offline)

1. **End to end on a tiny fixture corpus, gateway stubbed.** A `tmp_path` corpus of 2 short `.txt`
   units plus a stub gateway whose `chat(slot, messages, **kwargs)` returns a grounding JSON array
   (`[{"claim_index": 0, "verdict": "ungrounded", "provenances": [], "confidence": 0.9,
   "reason": "…"}]` — the format `parse_grounding_response` consumes,
   `grounding/prompts.py:34-41`, `:81-130`). Run the mode with `--limit 2`; assert the receipt's
   counts, `skipped is False`, the model ids, and that the guard's drop count is present.
2. **Corpus absent → clean skip.** Point `--corpus-dir` at a missing path: the mode prints the skip
   line, writes `"skipped": true`, and exits 0.

### 8.4 Acceptance criteria

```
uv run pytest tests/unit/test_grounding_corruption.py -q
uv run pytest tests/unit/test_grounding_harness.py tests/unit/test_grounding_harness_e2e.py -q
uv run python scripts/measure_slm_slots.py --grounding-accuracy --limit 20 --arm local --out docs/benchmarks/results/grounding-accuracy-local.json
uv run python scripts/measure_slm_slots.py --grounding-accuracy --limit 20 --arm cloud --out docs/benchmarks/results/grounding-accuracy-cloud.json
uv run pytest -m "fast or slow" -q                 # the whole offline suite stays green
```

Plus, checked by review (and by test 8.2.5):
- `src/openreview_cli/grounding/metrics.py` is byte-identical (`git diff --exit-code` on the path).
- The mode's receipt carries no CP/CR/CL value and no single aggregate score.
- Every negative in the receipt carries its generator and its guard status; none was kept after
  appearing verbatim in the cited clause.
- With `data/` absent (a fresh worktree, CI), the mode exits 0 and the rest of CI is unaffected.

---

## 9. Risks and things this design cannot settle

1. **Single-sample, non-deterministic models.** One run per label per arm; local and cloud replies
   vary. `--limit` is a smoke sample, not a benchmark; the report must say so. (Master plan §9's
   style: state the sample, do not imply a benchmark.)
2. **The cloud arm needs the OpenRouter key and its spend limit.** The last attempt failed with
   `403 Key limit exceeded` (record §1.6 / W10); the user reported buying more tokens, so the cloud
   arm may still be blocked at run time. The local arm is unaffected and is the one that runs first.
3. **Latency numbers are CPU-bound and machine-specific.** The local per-call figure is what the
   product's users pay; the receipt records the git sha and timestamp but not the machine. The
   report says the numbers are from one machine.
4. **Sentence extraction on numbered clause text.** The units are paragraphs, and a paragraph can
   contain a numbered sub-list; a "sentence" from it is still verbatim clause text, so the positive
   remains trivially grounded. This only affects how natural the claims read.
5. **`--limit 20` on 462 files** means the harness reads only the first 20 units across the first
   file(s) it visits (deterministic: sorted file names, then unit order). The full-corpus run in
   Phase 4 raises `--limit`; the receipt always states how many files were scanned.
6. **Uncertain verdicts can dominate.** `ground_claim` returns `UNCERTAIN` on a gateway error
   (`discriminator.py:113-115`) or an unparseable reply (`:117-120`). A run whose every call errored
   therefore produces zero caught **and** zero false rejects — which is why the receipt records the
   error/unparseable counts and the report must not present a high `caught_rate` from a run with
   many `uncertain` verdicts. (Pinned by test 8.2.7's shape, which reports the `uncertain` columns.)

---

## 10. Not in scope

- **No human-labelled grounding corpus.** That is a separate annotation task (master plan §10).
  The positives stay verbatim clause sentences, with that weakness stated in the report.
- **No change to the production metrics function.** `grounding/metrics.py` is left untouched
  (it is production-used: `grounding/discriminator.py:219`, exported at
  `grounding/__init__.py:14,40`). The harness neither calls it as a signal nor needs it.
- **No change to the production grounding path.** `CitationGroundingDiscriminator.ground_claim`,
  `ground_report`, the prompts, the strict/lenient filtering and the CLI defaults are all unchanged.
  The only production edit is the **additive** `unsupported_claim` in `grounding/corruption.py`.
- **No new top-level script** and **no new dependency.** The mode lives in
  `scripts/measure_slm_slots.py` and reuses its helpers (master plan T3.2, §12 ponytail item).
  Splitting helpers out of that file is explicitly deferred ("not now").
- **No CI job that requires the corpus.** CI exercises only the skip path.
- **No scoring of citation validity** (`anachronism`) or of claim categorisation (`category_swap`).
  Each would be a different harness with a different contract (§2.3).
- **No re-run of the retrieval or slot measurements here.** Those are Phase 4 items (master plan
  §7) and the CUAD retrieval harness does not exist yet.
- **No deletion of `tests/fixtures/grounding/seeded_claims.json` in this plan** — Phase 1 T1.7 owns
  that deletion; the harness merely makes the file unnecessary (record W7).
