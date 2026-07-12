# TUI Decisions

Recorded 2026-07-11. Design choices for the full interactive TUI.

## Architecture

| Decision | Choice | Rationale |
|----------|--------|-----------|
| TUI type | Full TUI (Textual) | Not questionary prompts. Multi-panel persistent app. |
| Framework | Textual | Rich ecosystem, same author as Rich (already installed). Supports tabs, panels, layouts, mouse, async. |
| Persistence | Session stays open until user Quits. | True app feel, not one-shot CLI. |

## Navigation

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Navigation style | Tab bar at top | Most familiar to non-technical users (browser-like). |
| Tabs | Home · Review · Clients · Playbooks · Settings · Quit | Covers all primary workflows. |

### Tab contents (high-level)

- **Home**: Dashboard — recent reviews + quick actions
- **Review**: New review wizard + past reviews list
- **Clients**: CRUD + client detail + per-client reviews
- **Playbooks**: List, import, detail, version history, diff
- **Settings**: Gateway setup, tier display, config edit, about

## Screen transitions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Confirmations (delete, cancel) | Modal overlay | Quick, don't lose context. |
| Settings / forms | Full screen | Enough room for forms, avoids cramped overlays. |
| Review result | Full screen | Clause list + detail needs space. |

## Home screen (Dashboard)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Recent reviews | Yes — last 5, clickable | Users re-open recent work most often. |
| Quick actions | New Review, Import Document, Open Last Result | 90% usage paths in two taps. |

## Review flow

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Mode selection | Grouped (not flat list of 22) | Easier scanning. Groups: Basic, Employment, Commercial, Specialized. |
| File picker | Filesystem browser (fzf-style) | Navigate dirs, type to filter. |
| File picker start dir | Current working directory | Predictable. User navigates from there. |
| Playbook picker | Optional, defaults to mode's default | Let user override but don't force. |
| Progress during review | Progress bar | Feedback during multi-agent pipeline (can take minutes). |

## Review result screen

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Primary view | Clause list + red flags | Most valuable output first. |
| Layout toggle | Split pane (list + detail) vs full scroll | User preference. |
| Post-review actions | Export memo (md/json/docx), Back to home | Common next steps. |

## Modes (22 product modes)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Display | Grouped by category | Less overwhelming than 22-item flat list. |
| Groups | Basic, Employment, Commercial, Specialized, Settlement | Matches product line. |

### Mode groups (preliminary)

**Basic**: PreCheck (NDA), PrivacyCheck (DPA)
**Employment**: HireCheck, WorkCheck, ConsultCheck, SubCheck
**Commercial**: DealCheck, LeaseCheck, LicenseCheck, IndemnityCheck, PartnerCheck, DistroCheck, FranchiseCheck, OpCheck, SponsorCheck
**Specialized**: LoICheck (LOI/MOU)
**Settlement**: SettlementCheck, SettlementCheck_v2, (remaining batch 3 modes)

*Note: Group boundaries are drafts — revisit when implementing.*

## Status bar

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Show | Current client (if set), Gateway status (icons) | Always-visible context. |

## Output & Export

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Export formats | md, json, docx | Same as current CLI. |
| Export trigger | Button in review result screen | Explicit action, not automatic. |

## Command descriptions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Show description on focus | One line max per command | When user highlights a menu item, show a brief description in the status bar. Reduces guesswork. |
| Location | Status bar (bottom) | Always visible, doesn't clutter the main area. |
| Description shows | Focused item only | The currently highlighted row's description. Updates as cursor moves. |

## Global UX patterns

| Pattern | Description | Where used |
|---------|-------------|------------|
| Type-to-filter | All lists with many items support typing to filter. Fzf-style. | Mode picker, file picker, playbook picker, client list, playbook list, past reviews. |

## Resolved open questions

| Question | Decision | Rationale |
|----------|----------|-----------|
| File picker — show hidden files? | Hide by default. Toggle with Ctrl-H. | Less noise. Ctrl-H is fzf convention. |
| Recent reviews — how many? | 5 | Fits dashboard without scrolling. Configurable later. |
| Gateway config | TUI wizard (step-by-step) | Easier for non-technical users. Panel comes later if requested. |
| Global search (`/`)? | Yes — include in v1 | Navigation power feature. Hits `.` for quick access. |
| Theme toggle? | No — dark mode only for v1 | Standard for terminal apps. Add later if requested. |
| Mouse support? | On by default | Textual default. Scroll and click work. No off switch needed for v1. |
| Status — 1 failing slot, show what? | Full detail (slot + provider + error) | One line is enough; multiple failures → count. |
| Status — gateway indicator clickable? | Yes → opens Settings > Gateway | Fast access to fix failures. |
| Pricing tier in status? | Mark as `—` (em-dash) for v1 | Slot reserved, implementation later. |
| Gateway wizard entry | Always 4 steps (slot, provider, model, key) | No skip from shortcuts. One code path, simpler. |
| Multi-slot with same provider | API key cached per-provider in auth.json | User enters key once per provider, not once per slot. Step 4 skipped when key exists. |

## Future considerations (not for v1)

- Multi-window / split-pane review comparison (dual-party)
- Batch review (multiple docs in one session)
- Real-time collaboration indicators
