# Deferred Items

Tracking items explicitly deferred from active specs pending external
prerequisites, constitutional amendments, or infrastructure not yet built.

---

## D-1: `--share-data` (Opt-In Anonymized Data Collection)

| Field | Value |
|-------|-------|
| **Deferred from** | NX-1 / spec 014 |
| **Deferred at** | 2026-07-03 |
| **Trigger** | Speckit Analyse stage — constitutional conflict (CRITICAL) |
| **Status** | Unblocked when constitution is amended |

### Description

An opt-in `--share-data` flag on `openreview precheck compare` that sends
anonymized comparison results (divergence classifications, PII-stripped
clause texts, confidence scores) to a research server. The goal is to
build the first public bilateral NDA comparison corpus — no paper
currently studies this problem (§6.7 of the blueprint).

Collected data would be:
- Anonymised: no filenames, timestamps, IPs, or user identifiers
- Opt-in only, revocable at any time
- Explained to the user with a clear prompt before first upload
- Excludes raw document text, only PII-stripped clause excerpts

### Blocking constraint

Constitution **§I (Privacy First)** and **§II (Local-First, CLI-Only)**:

> *"The tool never proxies data through any server it operates."*
> *"No outbound telemetry, analytics, or 'phone home' beyond the optional
> weekly model-registry refresh."*

`--share-data` would create a new outbound network path carrying data
beyond the registry refresh. This is a direct conflict with the
constitution as written.

### What would need to change to unblock

1. **Amend the constitution** to add a `Research Data Exception` to
   Principles I and/or II — something like:
   > *"Opt-in, anonymised research data collection is exempt from the
   > no-outbound-telemetry rule, provided the user explicitly consents
   > each session, all data is stripped of PII before transmission, and
   > the purpose (building a public corpus) is disclosed."*
2. **Restore `--share-data`** in the spec, plan, contracts, and tasks
   (currently struck through / removed across all artifacts)
3. **Implement** the data collection CLI flag, anonymisation pipeline,
   and upload endpoint
4. **Add integration tests** for the consent flow, anonymisation, and
   upload failure handling

### Spec details (from spec 014 §12, preserved for reference)

```markdown
- Users MAY opt-in via a `--share-data` flag to share anonymized
  comparison results (clause texts, divergence classifications,
  confidence scores) for research purposes.
- Opt-in SHALL be explicitly requested after the first `compare` run
  (not before). The prompt SHALL explain what is collected and that
  no PII or raw document text is included.
- Collected data SHALL be anonymized: no filenames, no timestamps,
  no IP addresses, no user identifiers.
- Only divergence classifications and stripped clause texts
  (PII already removed) SHALL be shared.
- The purpose is to build a corpus of bilateral NDA comparisons for
  improving future accuracy.
- Opt-in SHALL be revocable at any time.
```

Blueprint references: §11 (Speckit Seed), §6.7 (research gap).

### Spec artifacts referencing `--share-data`

| File | Status |
|------|--------|
| `specs/014-bilateral-comparison/spec.md §12` | Preserved, marked DEFERRED |
| `specs/014-bilateral-comparison/plan.md` | Mentioned in deferred notes |
| `specs/014-bilateral-comparison/contracts/cli-interface.md` | Line struck through |
| `specs/014-bilateral-comparison/tasks.md` | T056 struck through |

---

## D-2: Typer CLI Integration Tests ✅ RESOLVED

| Field | Value |
|-------|-------|
| **Deferred from** | NX-1 / spec 014 (US3) |
| **Deferred at** | 2026-07-03 |
| **Resolved at** | 2026-07-03 |
| **Resolved by** | Spec 015 (typer-cli-test-routing) |
| **Trigger** | Architectural limitation |
| **Status** | ✅ **Resolved** |

Tasks T050–T053, T055 could not pass positional document args to
subcommands because the `precheck` Typer callback had
`invoke_without_command=True` with a positional `document_path` arg,
which intercepted them.

**Fix (spec 015):** Changed `document_path` from `typer.Argument(None)`
to `typer.Option(None, "--document", "-d")` on the `precheck` callback.
7 subprocess-based integration tests now cover all previously-deferred
CLI flags. See `tests/integration/test_bilateral_flags.py` and
`specs/015-typer-cli-test-routing/`.
