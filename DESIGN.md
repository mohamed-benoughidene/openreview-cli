---
name: openreview
description: Privacy-preserving local-first contract review & analysis CLI & TUI
colors:
  primary: "#2563eb"
  primary-hover: "#1d4ed8"
  accent: "#0284c7"
  surface: "#1e1e2e"
  surface-boost: "#181825"
  neutral-text: "#cdd6f4"
  neutral-muted: "#a6adc8"
  status-green: "#22c55e"
  status-amber: "#f59e0b"
  status-red: "#ef4444"
  border-subtle: "#313244"
typography:
  display:
    fontFamily: "monospace"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  headline:
    fontFamily: "monospace"
    fontSize: "1.125rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "normal"
  title:
    fontFamily: "monospace"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "monospace"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "monospace"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "0.05em"
rounded:
  sm: "2px"
  md: "4px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral-text}"
    rounded: "{rounded.sm}"
    padding: "0 2"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-error:
    backgroundColor: "{colors.status-red}"
    textColor: "{colors.neutral-text}"
    rounded: "{rounded.sm}"
    padding: "0 2"
  button-success:
    backgroundColor: "{colors.status-green}"
    textColor: "{colors.neutral-text}"
    rounded: "{rounded.sm}"
    padding: "0 2"
---

# Design System: openreview

## Overview

**Creative North Star: "The Sovereign Ledger"**

OpenReview operates in the terminal as an uncompromising, privacy-first legal inspection instrument. Its visual presence is disciplined, high-contrast, and focused on rapid analytical comprehension. It eschews decorative graphical bloat in favor of clear information architecture, instant keyboard affordances, and unmistakable status signaling.

The system balances deep analytical density (clause text, confidence distributions, game-theoretic negotiation payoffs) with immediate operational clarity. In both the Typer CLI and Textual TUI, the interface communicates through calibrated typography, structured spatial bounding boxes, and an authoritative three-color risk classification system.

**Key Characteristics:**
- **Terminal-Native Precision**: High-contrast monospaced data grids, box-drawing containers, and deterministic layout scaling.
- **Three-Color Risk Semantics**: Uncompromising status triage using Green (Preferred/OK), Amber (Human Triage/Ambiguity), and Red (Walkaway/Critical).
- **Literal Text Fidelity**: Pure literal rendering (`markup=False`) guaranteeing uncorrupted legal clauses, bracketed party placeholders, and raw agreement text.
- **Zero-Latency Keyboard Choreography**: Every workflow action mapped to single-stroke hotkeys with explicit non-markup visual button hints.

## Colors

The OpenReview palette is anchored by deep terminal dark-mode surfaces, calibrated semantic risk indicators, and focused cobalt accents.

### Primary
- **Cobalt Accent** (`#2563eb`): Key interactive focus boundaries, selected tabs, modal borders, and primary progression actions.
- **Cobalt Deep** (`#1d4ed8`): Active/hover state for primary buttons and selection highlights.

### Secondary
- **Sky Focus** (`#0284c7`): Secondary interactive states, active list item highlights, and table header accents.

### Neutral
- **Deep Surface Base** (`#1e1e2e`): Background canvas for all TUI screens and container viewports.
- **Surface Boost** (`#181825`): Recessed containers, status dock backgrounds, and summary header bars.
- **Surface Border** (`#313244`): Structural bounding borders and split-pane dividers.
- **Text High-Contrast** (`#cdd6f4`): Primary reading text, clause text, and table cells.
- **Text Muted** (`#a6adc8`): Secondary metadata, timestamps, clause IDs, and context headers.

### Semantic Status
- **Status Green** (`#22c55e`): Preferred position match, high-confidence verification, passing checks (`● OK`).
- **Status Amber** (`#f59e0b` / `orange`): Ambiguous positions, low confidence, QA disagreements, grounding discrepancies (`⚠ AMBER`).
- **Status Red** (`#ef4444`): Walkaway violations, ungrounded assertions, failing stages (`● RED` / `✗`).

### Named Rules
**The Three-Color Triage Rule.** Every analyzed clause must strictly resolve to Green, Amber, or Red. Amber is never a warning to be suppressed—it is an explicit signal for human lawyer adjudication.

**The Textual Orange Rule.** In Textual CSS, the amber status must be mapped to valid CSS color keyword `orange` / `#f59e0b` (never invalid token `amber` or Rich's `dark_orange`).

## Typography

**Display Font:** System Monospace / Terminal Monospace (Fallback: `Courier New`, `Consolas`, `monospace`)
**Body Font:** System Monospace / Terminal Monospace
**Label/Mono Font:** System Monospace

**Character:** Utilitarian, rigorous, and strictly tabular. Terminal fonts ensure exact horizontal column alignment for complex multi-column legal comparison matrices.

### Hierarchy
- **Display** (Bold, 1.5rem / Large terminal headers, line-height 1.2): Screen titles and welcome headers.
- **Headline** (Bold, 1.125rem, line-height 1.3): Step titles, modal headers, section headers (`#recent-header`, `#egress-title`).
- **Title** (Bold, 1rem, line-height 1.4): Table column titles, tab labels, summary group headings.
- **Body** (Regular 400, 0.875rem, line-height 1.5, max 80–120ch): Clause text, legal agreement paragraphs, error logs, and detailed reasoning notes.
- **Label** (Semi-bold 600, 0.75rem, letter-spacing 0.05em, uppercase or title-case): Button action keys, status badges, confidence meters, and footer bindings.

### Named Rules
**The Literal Text Rule.** All clause text, bracketed variables (`[Party A]`, `[intentionally omitted]`), filenames, and user inputs must be rendered with `markup=False` or wrapped in Rich `Text(...)` primitives. Rich style parsing must never consume contract brackets.

## Layout

The spatial model conforms to terminal geometry (standard 80×24 up to full-screen 160×48+ columns).

- **Screen Viewport**: Full-height dock layout featuring a fixed top Header, dynamic scrollable central workspace (`1fr`), docked bottom action bar (`height: 3`), and a fixed system Footer.
- **Split-Pane Architecture**: Clause inspection uses a dual-pane layout (`#clause-list-pane` at `2fr` width and `#clause-detail-pane` at `3fr` width) with dynamic single-pane toggle (`l` key).
- **Adaptive Terminal Width**: Terminal tables and summary outputs dynamically query terminal dimensions via `shutil.get_terminal_size()`, adapting between 40-column compact widths and wide multi-column reports without text truncation.
- **Padding Rhythm**: Consistent 1-character vertical and 2-character horizontal padding (`padding: 1 2`) on containers, modal dialogs, and overview tables.

## Elevation & Depth

OpenReview is a flat-by-default terminal architecture. Depth is communicated strictly through tonal layering and structural line borders.

- **Tonal Layering**: Deep base canvas (`#1e1e2e`) topped by recessed container bars (`#181825`) and highlighted active rows (`#0284c7`).
- **Borders as Elevation**: Modals use thick solid borders (`border: thick $primary`) to signal modal focus and foreground elevation over dim backgrounds.
- **Zero Halo Rule**: No synthetic glow effects, blurry drop-shadows, or artificial decorations.

## Shapes

- **Corner Strategy**: Strict terminal block geometry (0px to 4px equivalent). Small 2px corner curvature for buttons and input fields where terminal renderers support anti-aliasing.
- **Box Borders**: Solid (`border: solid $primary`) and thick (`border: thick $primary`) ASCII/Unicode line borders for pane boundaries, tables, and modal dialogs.
- **Progress Glyphs**: Deterministic geometric symbols for 5-stage pipeline checklist (`○` pending, `●` active/running, `✓` complete, `✗` failed).

## Components

### Buttons
- **Shape**: Compact terminal block, padding `0 2`, min-width 12–14 cells.
- **Primary**: Background `#2563eb`, text `#cdd6f4`, text-style bold. Used for affirmative actions (`New review`, `Continue`, `Save`).
- **Success / Error**: Success (`#22c55e`) for `Accept (A)`, Error (`#ef4444`) for `Reject (R)` and `Quit`.
- **Default / Ghost**: Neutral background `$surface`, subtle border, highlighting on `:hover` and `:focus`.
- **Labeling Convention**: Keyboard shortcuts in parentheses, e.g. `Accept (A)`, `Cancel (Esc)`, `Done (Esc)`. Never use square brackets (`[A]`) which collide with markup parsers.

### Modals & Dialogs
- **Centered Dialogs**: Fixed width (60–72 columns), height auto, centered layout (`align: center middle`).
- **Egress Review Modal**: Pre-flight privacy disclosure detailing exact local vs. cloud slot destinations and redacting state before execution.
- **Annotate Modal**: Single-input popup for capturing custom reviewer notes per clause.

### Data Tables & Clause Lists
- **Columns**: Explicit unique column keys (`c-num`, `c-clause`, `c-decision`, `c-note`) preventing cell indexing errors.
- **Focus Isolation**: Overview tables set `can_focus = False` when paired with guided card workflows, ensuring navigation keys (`Up`/`Down`, `J`/`K`) drive the triage queue rather than trapping table cursor focus.

### Status Bar & Egress Counters
- **Docked Telemetry**: Docked horizontal status bar displaying active Client, Privacy Tier, Gateway status, and real-time live `#status-egress` cloud call counter.

## Do's and Don'ts

### Do:
- **Do** set `markup=False` on all `Label`, `Static`, and `ListItem` widgets that display clause text, file paths, or counterparty names.
- **Do** wrap arbitrary text cells in Rich `Text(text, no_wrap=True)` when building `rich.table.Table` or Textual `DataTable` rows.
- **Do** map amber status indicators to the valid Textual CSS color `orange` (`#f59e0b`).
- **Do** place key shortcuts in parentheses (`(A)`, `(R)`, `(Esc)`) on buttons.
- **Do** query `shutil.get_terminal_size()` for responsive terminal width calculation in CLI reports.
- **Do** support both guided card navigation and full overview table triage in the Amber Queue.

### Don't:
- **Don't** import `litellm` or heavy gateway modules at the top level of `tui/` modules.
- **Don't** use square brackets for button key hints (`[A]`, `[Enter]`).
- **Don't** emit raw multi-line stack traces for known user errors; format into clean single-line error messages with standard POSIX exit codes (0–5).
- **Don't** use `dark_orange` or `amber` in Textual CSS.
- **Don't** send unredacted contract text to cloud models or external APIs under any circumstances.
