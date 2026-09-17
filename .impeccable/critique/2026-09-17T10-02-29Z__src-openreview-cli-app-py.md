---
target_identity: "file:/home/mohamed/lab/openreview/src/openreview_cli/app.py"
target_fingerprint: "sha256:c79f9c8bbd7e1fee858a36df982f3bfb7af57fc59ea0a27bb5ea0fe9e6f5abd1"
target_path: /home/mohamed/lab/openreview/src/openreview_cli/app.py
timestamp: 2026-09-17T10-02-29Z
slug: src-openreview-cli-app-py
---
# OpenReview CLI & TUI Design Critique

**Target:** `src/openreview_cli/app.py` & `src/openreview_cli/tui/app.py`
**Date:** 2026-09-17
**Mode:** Operate
**Heuristic Score:** 19 / 40

## Critical Findings
1. **[P0] Unescaped Markup Deletion**: `Static` / `Label` widgets consume brackets; legal clauses with `[intentionally omitted]` or `[bracketed text]` have text deleted in the TUI.
2. **[P1] CLI Report Color Loss**: `StringIO` sink with `force_terminal=False` removes all ANSI colors from the terminal report.
3. **[P1] Amber Color Tag**: `[amber]` is not a valid Rich color tag, so amber clauses receive no color in the TUI.
4. **[P1] Inert Progress Bar**: `ProgressScreen` steps and `ProgressBar` never advance during multi-minute reviews.
5. **[P1] Exit Code Drift**: Documented exit codes (0–5) are not implemented consistently.
