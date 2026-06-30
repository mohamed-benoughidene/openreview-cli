# Draft Edits: 006-cli-ux-specification

## plan.md changes
No changes needed. The UX layer is slot-agnostic — it renders what it's given.

## tasks.md changes

### T058a — env var overlay
Current config keys include `model.reranking` as an env var override.

Add a note: `OPENREVIEW_MODEL_RERANKING` env var is defined but unused by default (reranking is optional). The loader should accept but not require it. Same as any other `OPENREVIEW_*` key — unknown keys are ignored at debug level.
