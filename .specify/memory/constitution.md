<!--
Sync Impact Report
==================
Version change: 1.1.0 → 1.2.0 (MINOR — GPU acceleration mandate + NLP model memory exemption)
Modified principles: III (Hardware-Bounded) — added GPU auto-detection rule and NLP model memory exemption rule
Added sections: Core Principles (I–V), Constraints, Development Workflow
Removed sections: none
Templates requiring updates: none — the current spec-kit templates have
  no principle-driven content that contradicts this constitution.
Deferred items: none.
-->

# openreview Constitution

This constitution is the source of truth for project governance. It defines
the non-negotiable rules that govern the design, implementation, and
operation of the `openreview` project (PyPI package `openreview-cli`,
Python import name `openreview_cli`, CLI command `openreview`).

When this constitution and a working specification disagree on a
**governance** matter, the constitution wins. When they disagree on
**technical detail**, the most current and reviewed specification wins.
Either form of conflict is resolved by amending the appropriate document
through the process in the Governance section.

## Core Principles

### I. Privacy First

PII is stripped from any data that leaves the user's machine. Raw contract
text is never written to logs. API keys live only in `auth.json` with
mode `600`, or in environment variables. The tool never proxies data
through any server it operates.

Rules:

- All PII detection and replacement MUST run locally before any external
  API call.
- Logging and debug output MUST redact or hash any unstripped text. PII
  placeholders (e.g. `[PARTY_A]`) are not PII and MAY appear in logs.
- `auth.json` MUST be created with `chmod 600` and MUST NOT be committed
  to version control.
- The only network request that may omit PII stripping is the optional
  weekly refresh of the cloud model registry, which carries no user
  data. All other outbound traffic is subject to PII stripping.
- A configuration in which every model slot is local (no network call is
  ever made by the tool) MUST be supported end-to-end.

Rationale: privacy posture is the project's primary market differentiator
and the only durable basis for the dual-license business model. Any
shortcut here is non-recoverable.

### II. Local-First, CLI-Only

The product is a local command-line tool. There is no web server, no
long-running daemon, no telemetry, and no first-party hosted service.
The only network path is a direct call from the user's machine to the
user's chosen AI provider.

Rules:

- No FastAPI, Flask, Django, Starlette, or any ASGI/WSGI framework as a
  runtime dependency.
- No background workers, schedulers, or persistent processes outside the
  lifetime of a single CLI invocation.
- No outbound telemetry, analytics, or "phone home" beyond the optional
  weekly model-registry refresh described in Principle I.
- The CLI MUST be operable on machines that are intermittently offline,
  provided every model slot is local.

Rationale: the project does not operate a service; adding one would
invert the license model and the privacy posture. Local-only is the
load-bearing constraint, not an aspiration.

### III. Hardware-Bounded

The reference target machine is an 8 GB RAM, 2-core CPU, no-GPU laptop.
The tool's peak memory budget is `<100 MB`; a hard floor of `<110 MB`
permits the last 10% only as headroom for incidental variance.

Rules:

- Document parsers MUST stream page-by-page (PDF), paragraph-by-paragraph
  (DOCX), or page-by-page (scanned PDF via Docling). Full-document loads
  are forbidden.
- Large collections (chunks, vectors, hierarchy nodes) MUST live in
  SQLite, not in-process dicts or lists.
- Hot-path data classes SHOULD use `@dataclass(slots=True)`.
- Heavy imports (PyMuPDF, python-docx, docling) MUST be lazy — imported
  only when the relevant code path is reached.
- API calls MUST be async and concurrent across playbook questions, and
  the CLI MUST show live progress.
- A regression that pushes peak memory above the 100 MB target by more
  than 10% is a release blocker.
- The PII detection NLP model (spaCy `en_core_web_lg`, ~500 MB loaded) is
  exempt from the <100 MB peak memory budget. The model is loaded once per
  CLI session and remains in memory. All other processing — document text,
  Presidio framework, regex recognizers, output buffers — must stay under
  the 100 MB peak. This exception is specific to Phase 3 (PII Stripping);
  any future NLP model of comparable size requires its own constitutional
  amendment.
- A GPU, if present on the host machine, MUST be detected and used for
  NLP model acceleration (spaCy `en_core_web_lg`) via Presidio's built-in
  CUDA/MPS auto-detection. No configuration is required from the user.
  The performance targets in this constitution (3-second per-document
  stripping, 100 MB budget) are CPU-based guarantees. GPU-accelerated
  machines will achieve faster processing at no additional memory cost.
  CPU fallback is automatic when no GPU is detected.

Rationale: local models already consume 2–5 GB on the reference machine.
The tool's slice is what is left. The budget is not negotiable; it is
the only thing that lets the product run side-by-side with local model
inference.

### IV. Dependency Minimalism

The dependency footprint is a liability. Standard library and platform
features come first. A new dependency is justified only by the feature
that needs it shipping in the same change.

Rules:

- The runtime dependency set MUST stay at or below what is required to
  implement the documented product modes. Adding a runtime dependency
  requires an amendment to the constitution.
- The following are **forbidden** in this project: langchain
  (unnecessary abstraction), llama-index (no clean fit for hierarchical
  chunking), FAISS (forces a second index file outside SQLite),
  spaCy for PII (requires custom NER training where Presidio works
  out of the box), sentence-transformers (Ollama covers embedding and
  reranking already), Click (Typer's type-hint DX is strictly better),
  loguru and structlog (overkill for a local CLI; stdlib `logging` is
  sufficient), FastAPI and Flask (no server; there is no server to run).
- Use `uv` exclusively for dependency management (no `pip`, `pip-tools`,
  `poetry`, or `pipx`). Add via `uv add <package>`, run `uv lock`, and
  commit the lockfile.
- Prefer `sqlite3`, `httpx`, `pathlib`, `asyncio`, `dataclasses`, and
  the stdlib `logging` module over equivalent third-party packages.
- Pydantic is permitted for configuration and gateway routing. Pydantic
  is not a license to introduce ORM-style abstractions.

Rationale: every dependency is paid for at install time, at startup
time, at memory time, and at maintenance time. The forbidden list
encodes a judgement the project has already made. Reversing a
rejection is a MINOR amendment; adding a new entry to the forbidden
list is a PATCH amendment.

### V. Spec-Driven, YAGNI

A feature is specified and reviewed before it is implemented. The
smallest change that works is the right change. Speculative work is
rejected at the pull-request level.

Rules:

- A non-trivial feature MUST be specified in a tracked artifact
  (specification document, issue, or design note) before landing in
  code. Trivial fixes are exempt.
- Specifications are changed in the same pull request family as the
  code that implements them, or in an earlier pull request. A pull
  request that contradicts an active specification without amending
  the specification is rejected.
- No speculative abstractions: no interface with one implementation,
  no factory for one product, no configuration knob for a value that
  never changes.
- Deletion is preferred over addition. Boring is preferred over clever.
- Every non-trivial change leaves one runnable check behind — a test
  case that fails if the logic breaks. Trivial one-liners need no test.
- Tools named in this constitution (e.g. `uv`, `ruff`, `mypy`,
  `pytest`) MAY be replaced by a successor that fills the same role.
  The rule is that the role must be filled; the specific tool is
  illustrative.

Rationale: the project's product specification is preliminary and may
change or be removed. Encoding "spec first, smallest change" as
governance — rather than as a soft guideline — prevents the
specification's tentative status from leaking into runtime surface
area or governance drift.

## Constraints

The following are non-negotiable technical and legal boundaries. They
hold regardless of feature priority.

- **Python version**: `>=3.12`. The minimum is fixed; bumping it is a
  MAJOR amendment.
- **Package manager**: `uv` exclusively. No `pip`, `pip-tools`,
  `poetry`, or `pipx` for this project.
- **Distribution**: PyPI package name `openreview-cli`; CLI command
  `openreview`; Python import name `openreview_cli`. Renaming any of
  these is a MAJOR amendment.
- **Licensing**: dual-licensed AGPL-3.0 + Commercial. A Contributor
  License Agreement is required for any code contribution that is
  merged. Dependencies with licenses incompatible with AGPL-3.0 are
  forbidden.
- **Hardware budget**: peak memory `<100 MB` with a hard floor of
  `<110 MB` (NLP model memory is exempt — see Principle III); cold
  startup `<1 s`; warm startup `<0.3 s`; parse time for a 50-page
  PDF `<3 s`. Exceeding the floor is a release blocker.
- **Privacy tier model**: three tiers — maximum (all-local),
  balanced (PII-stripped cloud where local is not feasible), and
  performance (cloud throughout with PII stripping). Removing a tier
  is a MAJOR amendment; adding a tier is a MINOR amendment.
- **Document formats**: PDF, DOCX, scanned PDF (OCR). Adding a format
  is a MINOR amendment; removing a format is a MAJOR amendment.
- **Forbidden dependency set**: see Principle IV. The list is
  reviewed on every dependency-add pull request.
- **Product modes**: the public CLI surface (one subcommand per
  product mode) is stable. Renaming or removing a mode is a MAJOR
  amendment.

## Development Workflow

- **Branches**: `feat/<description>`, `fix/<description>`,
  `docs/<description>`.
- **Commits**: Conventional Commits. Allowed types are `feat:`,
  `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, plus the standard
  `perf:`, `build:`, `ci:`. A commit that does not match one of these
  is rejected at review.
- **Pre-commit hooks**: linter (currently `ruff check --fix`),
  formatter check (currently `ruff format --check`), type checker
  (currently `mypy`), and a fast test subset (currently
  `pytest -m "not slow and not integration"`). All four MUST pass
  before a commit is accepted.
- **Continuous integration**: the CI pipeline runs the linter, the
  formatter check, the type checker, the full unit test suite, and
  a memory profile on every push and every pull request. A green
  CI is required to merge.
- **Release**: a `v*.*.*` tag triggers the build and publish pipeline.
  Cutting a release tag before the package's importable layout exists
  is forbidden — the publish step will fail.
- **Secrets**: `auth.json` is `chmod 600`, never committed, and
  excluded by default from cloud-storeable backups. Equivalent
  environment variables MAY be used instead of the file.
- **Public surface stability**: the CLI command tree, the document
  format set, the privacy tier set, the product mode set, and the
  configuration schema version are all part of the public surface
  and are protected by Principle IV's amendment rules.

## Research Grounding Rule
Before resolving any NEEDS CLARIFICATION, read `.specify/memory/verified-sources.md`.
All claims in research.md must reference a CONFIRMED item from that file.
Anything not found there must be written as UNVERIFIED with reason — never guessed.

## Task Grounding Rule
Before generating tasks.md, read `.specify/memory/task-context.md`.

- All file paths in tasks.md must match either EXISTS or NEW paths from task-context.md
- All library API references must match a CONFIRMED dep from task-context.md
- If task-context.md is missing, halt and emit: ERROR: run speckit.task-grounding first
- Flag any task referencing a MISMATCH path as ⚠️ PATH CONFLICT: <plan path> vs <actual path>

## Analysis Grounding Rule
Before running cross-artifact analysis, read `.specify/memory/analysis-context.md`.

Add a Detection Pass G to the standard analysis passes:

**G. Reality Check** (severity: HIGH if VERSION DRIFT or PATH CONFLICT, MEDIUM if NO ANCHOR)
- Any version number in plan.md that does not match a CONFIRMED anchor → flag as VERSION DRIFT
- Any file path in tasks.md that is neither EXISTS nor NEW in task-context.md → flag as PATH CONFLICT  
- Any API or function name in plan.md with NO ANCHOR in verified-sources.md → flag as UNVERIFIED API

If analysis-context.md is missing, add one CRITICAL finding to the report:
  C0 | Reality Check | CRITICAL | — | analysis-context.md not found | Run speckit.analysis-grounding before proceeding

## Governance

- **Supremacy**: this constitution is the project's source of truth on
  governance. Where it conflicts with any other document or convention
  on a governance matter, this file wins. Where it conflicts on
  technical detail, the most current and reviewed specification
  wins.
- **Amendments**: every change to this file goes through a pull
  request titled `docs: amend constitution to vX.Y.Z (rationale)`.
  The pull request description MUST cite the reason — new principle,
  principle redefinition, clarification, or alignment with a
  specification change — and MUST update the Sync Impact Report
  embedded at the top of the file.
- **Versioning policy**:
  - **MAJOR** (X.0.0) — removal or redefinition of an existing
    principle or section; any change that weakens a hard constraint.
  - **MINOR** (x.Y.0) — addition of a new principle, section, or
    materially expanded guidance.
  - **PATCH** (x.y.Z) — clarifications, wording, typo fixes,
    non-semantic refinements.
  - When the bump type is ambiguous, the pull request description
    MUST justify the chosen level.
- **Compliance review**: every implementation plan MUST include a
  Constitution Check section that lists each principle, marks it
  Pass / Violate / N/A, and justifies any N/A or violation. The
  check is a gate before any research phase and is re-checked after
  the design phase. A plan without a passing Constitution Check
  does not proceed.
- **Tool coupling**: this constitution names roles, not specific
  implementations, except where the implementation is itself the
  constraint (e.g. AGPL-3.0). Replacing a named tool with a
  successor that fills the same role is a PATCH amendment, provided
  the replacement does not change observable behaviour.

**Version**: 1.2.0 | **Ratified**: 2026-06-23 | **Last Amended**: 2026-06-25
