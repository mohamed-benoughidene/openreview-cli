# TUI Design Tree — openreview-cli

Recorded 2026-07-11. Consolidates all design decisions for the Textual-based full TUI.
Five persistent tabs (Home, Review, Clients, Playbooks, Settings) with modal overlays,
wizard flows, and a global status bar. Framework: [Textual](https://textual.textualize.io/)
(same author as Rich, already a dependency). Session persists until user quits.

---

## Global Elements

### Tab Bar (top, persistent)

```
┌─────────────────────────────────────────────────────────────────┐
│  [1] Home  [2] Review  [3] Clients  [4] Playbooks  [5] Settings  │  [6] Quit
└─────────────────────────────────────────────────────────────────┘
```

- Active tab highlighted; others dim.
- Clickable (mouse) or keyboard (Tab/Shift+Tab, 1-6).
- "Quit" is a button, not a tab — exits app.

### Status Bar (one line, below tab bar content, persistent)

```
 Client: Acme Corp  │  Gateway: ✓ All healthy  │  Tier: —
```

Gateway status variants:

| Condition | Display |
|-----------|---------|
| All slots healthy | `✓ All healthy` |
| 1 slot failing | `⚠ <slot> (<provider>): <error>` |
| 2-5 slots failing | `⚠ <N>/6 slots: <slot1>, <slot2>` |
| All slots failing | `✗ All slots unreachable` |
| Unconfigured | `— Not configured` |

- Gateway indicator clickable → navigates to Settings > Gateway.
- Tier always `—` for v1 (placeholder, implementation deferred).

### Description Bar (very bottom, one line, persistent)

```
 ─────────────────────────────────────────────────────────────────
 PreCheck — Analyze non-disclosure agreements.
```

- Shows one-line description of currently focused item.
- Updates as cursor moves across lists, buttons, tabs.
- Empty when nothing focusable is selected.

### Global Keybindings

| Key | Action |
|-----|--------|
| Tab / Shift+Tab | Cycle tabs forward/backward |
| 1 | Home tab |
| 2 | Review tab |
| 3 | Clients tab |
| 4 | Playbooks tab |
| 5 | Settings tab |
| 6 / Ctrl+Q | Quit (with confirmation if mid-action) |
| `/` | Open global search overlay |
| Up / Down | Navigate lists |
| Enter | Activate focused item / select |
| Escape | Go back / cancel modal / close overlay |
| Ctrl+C | Quit (confirmation if mid-action) |
| `?` | Show help overlay |
| F5 | Refresh current view |

---

## Home Tab

### Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ HOME ]                                                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Welcome to openreview                                    │   │
│  │  Document review toolkit for contracts and agreements.     │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Recent Reviews                                                     │
│  ┌─────┬──────────────┬──────────┬───────┬─────┬──────────┐        │
│  │  #  │ Filename     │ Date     │  🟢   │ 🟠  │  🔴     │ Mode  │
│  ├─────┼──────────────┼──────────┼───────┼─────┼──────────┤        │
│  │  1  │ nda-acme.pdf │07-10     │  3    │  2  │  1       │PreChk │
│  │  2  │ offer.pdf    │07-08     │  5    │  0  │  0       │HireChk│
│  │  3  │ lease.pdf    │07-05     │  1    │  4  │  3       │LeaseCh│
│  │  4  │ dpa-v2.pdf   │07-01     │  6    │  1  │  0       │PrivChk│
│  │  5  │ partner.pdf  │06-28     │  2    │  2  │  2       │PrtnChk│
│  └─────┴──────────────┴──────────┴───────┴─────┴──────────┘        │
│                                                                     │
│  Quick Actions                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐                │
│  │  [ + New review ]    │  │  [ ↑ Import document ]│                │
│  └──────────────────────┘  └──────────────────────┘                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Empty State

When no reviews exist:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Recent Reviews                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  No reviews yet. Start one with [ + New review ].            │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action |
|-----|--------|
| Enter on row | Open past review result |
| N | Trigger New review |
| I | Trigger Import document |

### Transitions

| From | Trigger | To |
|------|---------|----|
| Row click | Enter | Review result screen (Review tab, loaded) |
| New review | Click/N | Review tab > New review wizard |
| Import document | Click/I | File picker modal > parse > home |

---

## Review Tab

### Initial Layout (two panels)

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ REVIEW ]                                                        │
│                                                                     │
│  ┌──────────── 50% ───────────┐  ┌──────────── 50% ─────────────┐  │
│  │  New Review                 │  │  Past Reviews                  │  │
│  │                             │  │  ┌─────────────────────────┐   │  │
│  │  ┌─────────────────────┐    │  │  │ Filter: [           ]  │   │  │
│  │  │ [ Start new review ] │    │  │  ├─────────────────────────┤   │  │
│  │  └─────────────────────┘    │  │  │ nda-acme.pdf  07-10  │   │  │
│  │                             │  │  │ offer.pdf     07-08  │   │  │
│  │                             │  │  │ lease.pdf     07-05  │   │  │
│  │                             │  │  │ dpa-v2.pdf    07-01  │   │  │
│  │                             │  │  │ partner.pdf  06-28  │   │  │
│  │                             │  │  └─────────────────────────┘   │  │
│  └─────────────────────────────┘  └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### New Review Wizard — Step 1: Pick Mode

```
┌─────────────────────────────────────────────────────────────────────┐
│  New Review — Step 1/4: Select Mode                                 │
│                                                                     │
│  Filter: [p▲                                                       │
│                                                                     │
│  ┌─ Basic ────────────────────────────────────────┬────────────────┐│
│  │ ○ PreCheck           Analyze NDAs.             │                ││
│  │ ○ PrivacyCheck       Analyze DPAs.             │                ││
│  └────────────────────────────────────────────────┘                ││
│  ┌─ Employment ────────────────────────────────────┐               ││
│  │ ○ HireCheck          Analyze employment offers. │               ││
│  │ ○ WorkCheck          Analyze contractor agrmts. │               ││
│  │ ○ ConsultCheck       Analyze consulting agrmts. │               ││
│  │ ○ SubCheck           Analyze subcontractor doc. │               ││
│  └─────────────────────────────────────────────────┘               ││
│  ┌─ Commercial ────────────────────────────────────┐               ││
│  │ ○ DealCheck          Analyze commercial deals.  │               ││
│  │ ○ LeaseCheck         Analyze lease agreements.  │               ││
│  │ ○ LicenseCheck       Analyze license agreements.│               ││
│  │ ○ IndemnityCheck     Analyze indemnity clauses. │               ││
│  │ ○ PartnerCheck       Analyze partnership agrmts.│               ││
│  │ ○ DistroCheck        Analyze distribution docs. │               ││
│  │ ○ FranchiseCheck     Analyze franchise agrmts.  │               ││
│  │ ○ OpCheck            Analyze operating agrmts.  │               ││
│  │ ○ SponsorCheck       Analyze sponsorship docs.  │               ││
│  └─────────────────────────────────────────────────┘               ││
│  ┌─ Specialized ───────────────────────────────────┐               ││
│  │ ○ LoICheck          Analyze LOIs / MOUs.        │               ││
│  └──────────────────────────────────────────────────┘               ││
│  ┌─ Settlement ─────────────────────────────────────┐              ││
│  │ ○ SettlementCheck   Analyze settlement agrmts.   │              ││
│  │ (more)                                           │              ││
│  └──────────────────────────────────────────────────┘              ││
│                                                                     │
│                                              [ Next → ]  [ Cancel ] │
└─────────────────────────────────────────────────────────────────────┘
```

- Groups expand/collapse on click.
- Type-to-filter narrows by mode name and description across all groups.
- Description bar shows mode's one-line description on focus.

### New Review Wizard — Step 2: Pick Document

```
┌─────────────────────────────────────────────────────────────────────┐
│  New Review — Step 2/4: Select Document  (or type path directly)    │
│                                                                     │
│  Path: [/home/user/projects/contracts/                    [Browse]] │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ../                                                          │  │
│  │  nda-acme.pdf                                                 │  │
│  │  nda-supplier.pdf                                             │  │
│  │  offer-lead-engineer.docx                                     │  │
│  │  lease-warehouse.pdf                                          │  │
│  │  contracts/                                                   │  │
│  │  legal/                                                       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Filter: [nda▲                                                     │
│                                                    [ ← Back ] [ Next → ] │
└─────────────────────────────────────────────────────────────────────┘
```

- File picker modal (full-screen overlay, same visual).
- Directory navigation: Enter on directory enters it, `..` goes up.
- Type-to-filter narrows visible entries (fzf-style — searches filename).
- Ctrl+H toggles hidden file visibility.
- Start at CWD. User can also type absolute/relative path directly in the Path field.
- Browse button opens the file picker at the current path.
- Shows only supported extensions (.pdf, .docx, .txt) by default.

### New Review Wizard — Step 3: Pick Playbook

```
┌─────────────────────────────────────────────────────────────────────┐
│  New Review — Step 3/4: Select Playbook (optional)                  │
│                                                                     │
│  Mode selected: PreCheck                                            │
│                                                                     │
│  ○ Use default for PreCheck  ─────────────────────────────────────  │
│                                                                     │
│  ○ Custom playbook:                                                 │
│  Filter: [                                                         │
│                                                                     │
│  ┌──────────────┬────────┬───────┬──────────────────────────────┐   │
│  │ Playbook ID  │ Mode   │ Vers  │ Description                  │   │
│  ├──────────────┼────────┼───────┼──────────────────────────────┤   │
│  │ precheck-nda │ PreChk │ v2    │ Standard NDA categories      │   │
│  │ precheck-v2  │ PreChk │ v1    │ Legacy NDA categories        │   │
│  │ hirecheck    │ HireChk│ v3    │ Employment agreement review   │   │
│  │ deal-v2      │ DealChk│ v2    │ Commercial deal categories    │   │
│  └──────────────┴────────┴───────┴──────────────────────────────┘   │
│                                                                     │
│                                                   [ ← Back ] [ Next → ] │
└─────────────────────────────────────────────────────────────────────┘
```

- "Use default for [Mode]" is pre-selected.
- Custom playbook list filtered by current mode by default; can clear filter to see all.
- Description bar shows playbook description on hover.

### New Review Wizard — Step 4: Confirm and Run

```
┌─────────────────────────────────────────────────────────────────────┐
│  New Review — Step 4/4: Confirm                                     │
│                                                                     │
│  ┌─── Review Summary ──────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  Mode:          PreCheck                                     │    │
│  │  Document:      nda-acme.pdf (3 pages)                       │    │
│  │  Size:          142 KB                                       │    │
│  │  Playbook:      precheck-nda v2 (default for PreCheck)       │    │
│  │  PII stripping: Enabled                                      │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  Options:                                                            │
│  ☐ Override model                                                    │
│  ☐ Disable PII stripping                                             │
│                                                                      │
│  ┌──────────────────────┐  ┌──────────────────────┐                  │
│  │  [ ← Back ]          │  │  [ ▶ Run review ]    │                  │
│  └──────────────────────┘  └──────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────┘
```

- "Override model" checkbox → opens model picker (steps 2-4 of gateway wizard).
- "Disable PII stripping" checkbox → warns about data sent to provider.

### Progress Screen

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ REVIEW ]  Running PreCheck...                                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  30%            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Steps:                                                             │
│    ✅  1/5  Parsing document                                        │
│    ⏳  2/5  Stripping PII  ───                                     │
│    ⬜  3/5  Extracting clauses                                      │
│    ⬜  4/5  QA verification                                         │
│    ⬜  5/5  Building report                                         │
│                                                                     │
│  Elapsed: 00:12                                                    │
│                                                                     │
│  ┌──────────────────────┐                                           │
│  │  [ Cancel review ]   │                                           │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

- Current step streaming-style details shown inline (e.g., extracted clause count).
- Cancel → confirmation modal ("Cancel in-progress review? Results will be lost.").
- On failure: step marked ❌, error shown, [Back] and [Retry] buttons.

### Result Screen

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ REVIEW ]  PreCheck — nda-acme.pdf                  [Export ▼]     │
│                                                                     │
│  ┌────────────── 40% ──────────────┬────────────── 60% ───────────┐ │
│  │  Clauses                      │  Clause: 3.2 — Confidentiality│ │
│  │  ┌─────────────────────────┐   │                               │ │
│  │  │ 🟢 1.1  Definitions     │   │  Duration: 5 years from       │ │
│  │  │ 🟢 1.2  Scope           │   │  effective date.              │ │
│  │  │ 🟡 2.1  Payment Terms   │   │                               │ │
│  │  │ 🔴 3.1  Liability Cap  │   │  ⚠ Liability cap at $50K may │ │
│  │  │ 🔴 3.2  Confidentiality│   │  be too low for this deal.    │ │
│  │  │ 🟢 4.1  Termination     │   │  Consider negotiating to      │ │
│  │  │ 🟢 5.1  Governing Law  │   │  at least $250K or 1x fees.   │ │
│  │  │ 🟡 6.1  Dispute Res.   │   │                               │ │
│  │  └─────────────────────────┘   │  Context: Section 3.2 para 2   │ │
│  │                                │                               │ │
│  │  ════════════════════════      │  ┌─────────────────────────┐  │ │
│  │  Summary: 🟢 4  🟡 2  🔴 2    │  │ Raw clause text         │  │ │
│  │  ════════════════════════      │  └─────────────────────────┘  │ │
│  └────────────────────────────────┴─────────────────────────────────┘ │
│                                              [ Back to Home ]         │
└─────────────────────────────────────────────────────────────────────┘
```

- Left panel: filterable clause list (type-to-filter).
- Right panel: clause detail — assessment, explanation, context, raw text.
- Toggle button to switch to full-screen scroll view (single pane, clause + detail stacked).
- Export button dropdown: md, json, docx.
- Summary bar always visible at bottom of left panel.

### Past Reviews — Result View

Same result screen as above, but loaded from stored data rather than running pipeline.

### Keybindings (Review tab — result screen)

| Key | Action |
|-----|--------|
| Tab / Shift+Tab | Toggle focus between clause list and detail pane |
| Up/Down | Navigate clauses |
| F | Toggle full-screen / split layout |
| E | Open export menu |
| H | Navigate back to Home |

---

## Clients Tab

### Main List

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ CLIENTS ]                                                       │
│                                                                     │
│  Filter: [ae                                                     │
│                                                                     │
│  ┌──────────┬────────────────────────────┬───────────────┐          │
│  │ ID       │ Name                       │ Reviews       │          │
│  ├──────────┼────────────────────────────┼───────────────┤          │
│  │ acme-corp │ Acme Corporation           │ 3             │          │
│  │ beta-ltd  │ Beta Engineering Ltd        │ 1             │          │
│  │ gamma-llc │ Gamma Logistics LLC         │ 0             │          │
│  └──────────┴────────────────────────────┴───────────────┘          │
│                                                                     │
│  ┌──────────────────────┐                                           │
│  │  [ + Add client ]   │                                           │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

- Type-to-filter searches both ID and name columns.
- Enter on row → client detail.

### Client Detail

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ CLIENTS ]  Acme Corporation                                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ID:           acme-corp                                     │   │
│  │  Name:         Acme Corporation                              │   │
│  │  Notes:        Primary NDA partner.                          │   │
│  │  Created:      2026-06-15                                    │   │
│  │  Total Reviews: 3                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Reviews                                                           │
│  ┌──────────────┬──────────┬──────────┬───────┬─────┐              │
│  │ Filename     │ Date     │ Mode     │ 🟡    │ 🔴  │              │
│  ├──────────────┼──────────┼──────────┼───────┼─────┤              │
│  │ nda-acme.pdf │ 2026-07-10│ PreCheck │ 2     │ 1   │              │
│  │ nda-v2.pdf   │ 2026-06-20│ PreCheck │ 1     │ 0   │              │
│  │ msa.pdf      │ 2026-06-15│ DealCheck│ 3     │ 2   │              │
│  └──────────────┴──────────┴──────────┴───────┴─────┘              │
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                            │
│  │ [ Edit ] │ │ [ Delete ]│ │ [ Back ] │                            │
│  └──────────┘ └──────────┘ └──────────┘                            │
└─────────────────────────────────────────────────────────────────────┘
```

- Review row click → opens result screen (same as Review tab).
- Description bar: "Acme Corporation — 3 reviews, last 2026-07-10."

### Add/Edit Client Form (full screen)

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ CLIENTS ]  Add Client / Edit Client                              │
│                                                                     │
│                                                                     │
│   ID:     [acme-corp                           ]                    │
│           (lowercase, hyphens allowed, no spaces)                   │
│                                                                     │
│   Name:   [Acme Corporation                    ]                    │
│                                                                     │
│   Notes:  [Primary NDA partner.                ]                    │
│           (optional)                                                │
│                                                                     │
│                                                                     │
│                                                                     │
│                                                                     │
│  ┌──────────┐ ┌──────────┐                                          │
│  │ [ Save ] │ │ [ Cancel ]│                                          │
│  └──────────┘ └──────────┘                                          │
│                                                                     │
│  (Tab between fields. Enter saves from any field. Esc cancels.)     │
└─────────────────────────────────────────────────────────────────────┘
```

- ID field: auto-lowercase, only `[a-z0-9-]`, validates on save.
- Tab / Shift+Tab cycles fields.
- Enter triggers Save (from any field).
- Escape cancels (with confirmation if dirty).
- Mode: edit mode pre-fills existing values.

### Delete Confirmation Modal

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         ┌──────────────────────┐                    │
│                         │  Delete Client       │                    │
│                         │                      │                    │
│                         │  Delete "Acme Corp"? │                    │
│                         │  3 reviews will be   │                    │
│                         │  orphaned.           │                    │
│                         │                      │                    │
│                         │  ☐ Also delete all    │                    │
│                         │    reviews (irrev.)   │                    │
│                         │                      │                    │
│                         │  [ Cancel ] [ Delete ]│                    │
│                         └──────────────────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

- Centered modal, backdrop dims behind.
- If client has reviews, checkbox to also delete them.
- Warning changes based on checkbox state.

---

## Playbooks Tab

### Main List

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ PLAYBOOKS ]                                                     │
│                                                                     │
│  Filter: [pre                                                   │
│  Mode: [ All Modes ▼ ]                                             │
│                                                                     │
│  ┌──────────────┬──────────┬───────┬────────┬─────────────────────┐ │
│  │ ID           │ Mode     │ Vers  │ ★ Cur  │ Description         │ │
│  ├──────────────┼──────────┼───────┼────────┼─────────────────────┤ │
│  │ precheck-nda │ PreCheck │ v2    │ ★      │ Standard NDA review  │ │
│  │ precheck-nda │ PreCheck │ v1    │        │ Legacy NDA review    │ │
│  │ hirecheck    │ HireCheck│ v3    │ ★      │ Employment agreement  │ │
│  │ deal-v2      │ DealCheck│ v2    │ ★      │ Commercial deal rev.  │ │
│  │ privacy      │ PrivChk  │ v1    │ ★      │ DPA review            │ │
│  └──────────────┴──────────┴───────┴────────┴─────────────────────┘ │
│                                                                     │
│  ┌──────────────────────┐                                           │
│  │  [ + Import playbook ]│                                           │
│  └──────────────────────┘                                           │
└─────────────────────────────────────────────────────────────────────┘
```

- ★ column indicates which version is current for that mode.
- Type-to-filter narrows by ID and description.
- Mode dropdown filters to one mode group.

### Playbook Detail

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ PLAYBOOKS ]  precheck-nda v2                                     │
│                                                                     │
│  ID:     precheck-nda                                               │
│  Mode:   PreCheck                                                   │
│  Version: v2 (current)                                              │
│                                                                     │
│  Categories                                                         │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │ 1. Term of Agreement          Default: Unfavourable           │   │
│  │    How long the NDA keeps info confidential.                 │   │
│  │                                                              │   │
│  │ 2. Definition of Confidential   Default: Acceptable          │   │
│  │    What counts as confidential info.                         │   │
│  │                                                              │   │
│  │ 3. Permitted Disclosures       Default: Acceptable           │   │
│  │    Exceptions to confidentiality.                            │   │
│  │                                                              │   │
│  │ 4. Return of Materials         Default: Favourable           │   │
│  │    What happens to confidential info after term.             │   │
│  │                                                              │   │
│  │ 5. Liability Cap               Default: Unfavourable         │   │
│  │    Cap on damages for breach of NDA.                         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────┐                    │
│  │[ View versions]│ │ [ Diff vs v1]│ │ [ Back ] │                    │
│  └──────────────┘ └──────────────┘ └──────────┘                    │
└─────────────────────────────────────────────────────────────────────┘
```

- "Diff vs v1" opens diff view (full-screen) between this version and v1.

### Version History

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ PLAYBOOKS ]  precheck-nda — Version History                      │
│                                                                     │
│  ┌──────────┬────────────┬──────────┬────────────────────────────┐  │
│  │ Version  │ Date       │ Current  │ Actions                    │  │
│  ├──────────┼────────────┼──────────┼────────────────────────────┤  │
│  │ v2       │ 2026-07-01 │ ★        │ [Unset current] [Diff vs v1]│  │
│  │ v1       │ 2026-05-15 │          │ [Set as current]           │  │
│  └──────────┴────────────┴──────────┴────────────────────────────┘  │
│                                                                     │
│  ┌──────────┐                                                       │
│  │ [ Back ] │                                                       │
│  └──────────┘                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

- "Set as current" → confirmation modal ("Set v1 as current for PreCheck?").
- "Unset current" → confirmation modal ("Remove current marker from v2?").

### Diff View (full screen)

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ PLAYBOOKS ]  Diff: precheck-nda v1 → v2                          │
│                                                                     │
│  ┌─ Added ─────────────────────────────────────────────────────────┐│
│  │  Category: "Return of Materials" (pos 4)                       ││
│  │  Default: Favourable                                            ││
│  │  "What happens to confidential info after the term ends."      ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─ Changed ───────────────────────────────────────────────────────┐│
│  │  Category "Term of Agreement" (pos 1)                          ││
│  │    Default: Favourable  →  Unfavourable                         ││
│  │  Exemplar text: Updated to reflect 5-year industry standard.    ││
│  └─────────────────────────────────────────────────────────────────┘│
│  ┌─ Removed ───────────────────────────────────────────────────────┐│
│  │  Category: "Exclusivity" (was pos 6)                            ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
│                                               [ Esc: Back ]         │
└─────────────────────────────────────────────────────────────────────┘
```

- Added (green), changed (yellow), removed (red) sections.
- Scrollable if many differences.
- Description bar shows diff line details.

### Import Playbook Form

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ PLAYBOOKS ]  Import Playbook                                     │
│                                                                     │
│  YAML File: [/home/user/playbooks/custom-nda.yaml     [ Browse ]]  │
│  ─────────────────────────────────────────────────────────            │
│  Mode:  [ PreCheck ▼ ]                                              │
│  ─────────────────────────────────────────────────────────            │
│  Validation: ✅ Valid playbook (3 categories)                       │
│                                                                     │
│  Preview:                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  1. Term of Agreement          Default: Favourable            │   │
│  │  2. Definition of Confidential  Default: Acceptable           │   │
│  │  3. Permitted Disclosures     Default: Acceptable             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Will be imported as: precheck-nda v3                               │
│                                                                     │
│                                            ┌──────────┐ ┌──────────┐│
│                                            │ [ Cancel ]│ │[Import as││
│                                            │           │ │  v3 ]   ││
│                                            └──────────┘ └──────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

- Mode auto-detected from filename but editable.
- Validation runs on file selection (parses YAML, checks structure).
- Preview shows parsed categories.
- Version auto-incremented from existing versions of same playbook ID.
- Browse button opens file picker modal (yaml/yml only).

---

## Settings Tab

### Two-Panel Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  [ SETTINGS ]                                                      │
│                                                                     │
│  ┌────────────── 30% ───────────┬────────────── 70% ─────────────┐  │
│  │  Sections                   │  [Content panel — see below]     │  │
│  │                             │                                  │  │
│  │  > Gateway                  │                                  │  │
│  │    Configuration            │                                  │  │
│  │    Pricing Tier             │                                  │  │
│  │    About                    │                                  │  │
│  └─────────────────────────────┴──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

- Left list: sections. Click/Enter → right panel updates.
- Active section marked with `>`.

### Settings > Gateway Content

```
┌─────────────────────────────────────────────────────────────────────┐
│  Gateway Configuration                                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Current Setup                                               │   │
│  │                                                              │   │
│  │  Reasoning:   OpenAI  →  gpt-4o         ✓ healthy            │   │
│  │  Extraction:  OpenAI  →  gpt-4o-mini    ✓ healthy            │   │
│  │  Embedding:   Ollama  →  nomic-embed     ✓ healthy           │   │
│  │  Reranking:   — not configured          ⚠                    │   │
│  │  Graph:      — not configured                               │   │
│  │  Grounding:  — not configured                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────┐ ┌──────────────────────┐               │
│  │  [ Run setup wizard ] │ │  [ Configure slot... ▼ ]              │
│  └────────────────────────┘ └──────────────────────┘               │
│                                                                     │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

- Status column shows ✓ healthy, ⚠ error, or — not configured.
- "Configure slot..." dropdown lets user pick specific slot to configure.
- Run setup wizard starts the 4-step gateway wizard.

### Settings > Configuration Content

```
┌─────────────────────────────────────────────────────────────────────┐
│  Configuration                                                      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Key                    │ Value                  │ Default   │   │
│  ├─────────────────────────┼────────────────────────┼───────────┤   │
│  │  api.timeout           │ 30                     │ 30        │   │
│  │  pii.threshold         │ 0.7                    │ 0.5       │   │
│  │  storage.path           │ ~/.openreview/         │ ~/.openr.. │   │
│  │  review.default_mode    │ precheck               │ precheck  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────┐ ┌──────────────────────┐                   │
│  │  [ Edit selected ] │ │  [ Reset to default ] │                   │
│  └────────────────────┘ └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘
```

- Enter on row or [Edit selected] → full-screen form for that key (name, value, description).
- [Reset to default] → confirmation modal, resets to factory default.

### Settings > Pricing Tier Content

```
┌─────────────────────────────────────────────────────────────────────┐
│  Pricing Tier                                                       │
│                                                                     │
│  Current tier: Free (usage-based billing — tiers coming later)      │
│                                                                     │
│  ┌─── Usage (this month) ──────────────────────────────────────┐    │
│  │                                                              │    │
│  │  Prompt tokens:     42,350                                   │    │
│  │  Completion tokens:  8,120                                   │    │
│  │  Estimated cost:    $0.42                                    │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                     │
│  ┌─── Available Plans ─────────────────────────────────────────┐    │
│  │                                                              │    │
│  │  Free        — Current plan                                  │    │
│  │  Pro         — Not available yet                             │    │
│  │  Enterprise  — Not available yet                             │    │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

- Tier is display-only for v1. Upgrades marked "Not available yet".
- Usage stats from local tracking (not server).

### Settings > About Content

```
┌─────────────────────────────────────────────────────────────────────┐
│  About                                                              │
│                                                                     │
│  openreview-cli v0.1.0                                             │
│  License: AGPL-3.0 (with commercial option)                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Paths                                                       │   │
│  │  Config:  ~/.openreview/config.yaml     [📋 Copy]            │   │
│  │  Data:    ~/.openreview/data/           [📋 Copy]            │   │
│  │  Log:     ~/.openreview/logs/app.log    [📋 Copy]            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  URLs                                                        │   │
│  │  Repository: github.com/mohamed-benoughidene/openreview      │   │
│  │  Issues:     github.com/mohamed-benoughidene/openreview/issues│  │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  Textual v0.67.0  |  Python 3.12.3  |  Linux                       │
└─────────────────────────────────────────────────────────────────────┘
```

- Copy buttons copy path/URL to system clipboard.

---

## Modal Screens

All modals are full-screen overlays with translucent backdrop behind.

### File Picker Modal (full-screen overlay)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Select File                                     [Esc: Cancel]│  │
│  │                                                              │   │
│  │  Path: [/home/user/projects/                       ]         │   │
│  │                                                              │   │
│  │  Filter: [nda                                          ]    │   │
│  │                                                              │   │
│  │  ┌───────────────────────────────────────────────────────┐   │   │
│  │  │  📁  ../                                              │   │   │
│  │  │  📁  contracts/                                       │   │   │
│  │  │  📁  legal/                                           │   │   │
│  │  │  📄  nda-acme.pdf                                    │   │   │
│  │  │  📄  nda-supplier.pdf                                │   │   │
│  │  │  📄  offer-lead-engineer.docx                        │   │   │
│  │  │  📄  lease-warehouse.pdf                             │   │   │
│  │  └───────────────────────────────────────────────────────┘   │   │
│  │                                                              │   │
│  │  ⚡ Type to filter | Ctrl+H: toggle hidden files              │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

- Path field: type absolute/relative path directly, press Enter.
- File list: navigate with arrows, Enter to select file or enter directory.
- Ctrl+H toggles hidden file visibility.
- Shows only supported file types (.pdf, .docx, .txt for document picker; .yaml, .yml for playbook picker).

### Confirmation Dialog (centered modal)

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│                         ┌──────────────────────┐                    │
│                         │  Confirm Delete       │                    │
│                         │                      │                    │
│                         │  Permanently delete   │                    │
│                         │  this client?         │                    │
│                         │                      │                    │
│                         │  ⚠ 3 reviews will    │                    │
│                         │  become orphaned.     │                    │
│                         │                      │                    │
│                         │  ☐ Also delete all    │                    │
│                         │    reviews (irrev.)   │                    │
│                         │                      │                    │
│                         │  [Cancel]  [Delete]   │                    │
│                         └──────────────────────┘                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Help Overlay (full-screen)

```
┌─────────────────────────────────────────────────────────────────────┐
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Keyboard Shortcuts                              [Esc: Close] │  │
│  │                                                              │   │
│  │  ┌─────────────┬────────────────────────────────────────┐    │   │
│  │  │ Key         │ Action                                 │    │   │
│  │  ├─────────────┼────────────────────────────────────────┤    │   │
│  │  │ 1-5         │ Switch to tab 1-5                     │    │   │
│  │  │ Tab/Shift+Tab │ Cycle tabs                           │    │   │
│  │  │ /           │ Open global search                    │    │   │
│  │  │ ↑ ↓         │ Navigate lists                        │    │   │
│  │  │ Enter       │ Activate / select                     │    │   │
│  │  │ Esc         │ Go back / cancel                      │    │   │
│  │  │ Ctrl+C      │ Quit app                              │    │   │
│  │  │ ?           │ This help overlay                     │    │   │
│  │  │ Ctrl+H      │ Toggle hidden files (file picker)     │    │   │
│  │  └─────────────┴────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Wizard Steps Detail

### New Review Wizard (4 steps, sequential)

| Step | Screen | Key elements |
|------|--------|--------------|
| 1 | Pick Mode | Grouped list (5 groups, 22 modes), type-to-filter, expand/collapse groups |
| 2 | Pick Document | File picker (directory nav, type-to-filter, Ctrl+H toggle hidden) |
| 3 | Pick Playbook | Optional override, filtered by mode, "Use default" pre-selected |
| 4 | Confirm & Run | Summary table, checkboxes (override model, disable PII), Run button |

### Gateway Setup Wizard (4 steps, sequential)

| Step | Screen | Key elements |
|------|--------|--------------|
| 1 | Pick Slot | reasoning, extraction, embedding, reranking, graph, grounding |
| 2 | Pick Provider | Type-to-filter, shows key requirement indicator |
| 3 | Pick Model | Type-to-filter, shows context window + ★ recommended marker |
| 4 | API Key Entry | Text field (masked), [Verify] button tests key, shows success/error |

### Gateway Wizard — Full Visual (Step 1)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Gateway Setup — Step 1/4: Select Slot                              │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ○  reasoning        LLM calls for chain-of-thought          │   │
│  │  ○  extraction       LLM calls for structured extraction     │   │
│  │  ○  embedding        Text-to-vector conversion               │   │
│  │  ○  reranking        Result re-ranking (optional)            │   │
│  │  ○  graph            Knowledge graph queries (optional)      │   │
│  │  ○  grounding        Fact-checking lookups (optional)        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                                                   [ Next → ] [ Cancel ] │
└─────────────────────────────────────────────────────────────────────┘
```

### Gateway Wizard — Step 2 (Pick Provider)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Gateway Setup — Step 2/4: Select Provider                          │
│  Slot: reasoning                                                    │
│                                                                     │
│  Filter: [op                                                     │
│                                                                     │
│  ┌────────────────────────────────────┬────────────────────────┐   │
│  │ Provider          │ Key Required   │ Description             │   │
│  ├────────────────────────────────────┼────────────────────────┤   │
│  │ ○ OpenAI          │ ✓ API key     │ High-quality reasoning  │   │
│  │ ○ Anthropic       │ ✓ API key     │ Strong for extraction   │   │
│  │ ○ Google Gemini   │ ✓ API key     │ Multi-modal support     │   │
│  │ ○ Ollama (local)  │ ✗ No key      │ Run models locally      │   │
│  └────────────────────────────────────┴────────────────────────┘   │
│                                                                     │
│                                                   [ ← Back ] [ Next → ] │
└─────────────────────────────────────────────────────────────────────┘
```

### Gateway Wizard — Step 3 (Pick Model)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Gateway Setup — Step 3/4: Select Model                             │
│  Slot: reasoning  →  Provider: OpenAI                               │
│                                                                     │
│  Filter: [gpt-4                                                  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Model ID             │ Context  │ Recommended                │   │
│  ├──────────────────────────────────────────────────────────────┤   │
│  │ ★ gpt-4o             │ 128K     │ ✓ Best for reasoning       │   │
│  │ ○ gpt-4o-mini        │ 128K     │ (cheaper, slightly weaker) │   │
│  │ ○ gpt-4-turbo        │ 128K     │                           │   │
│  │ ○ gpt-3.5-turbo      │ 16K      │ (deprecated)              │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                     │
│                                                   [ ← Back ] [ Next → ] │
└─────────────────────────────────────────────────────────────────────┘
```

### Gateway Wizard — Step 4 (API Key Entry)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Gateway Setup — Step 4/4: API Key                                  │
│  Slot: reasoning  →  Provider: OpenAI  →  Model: gpt-4o             │
│                                                                     │
│  OpenAI requires an API key to use gpt-4o.                          │
│                                                                     │
│  API Key: [••••••••••••••••••••••••••••••••••]  [Toggle visibility]│
│                                                                     │
│  ┌────────────────────────┐                                         │
│  │  [ Verify connection ] │                                         │
│  └────────────────────────┘                                         │
│                                                                     │
│  Key will be stored in auth.json (chmod 600).                       │
│                                                                     │
│                                                      [ ← Back ] [ Finish ] │
└─────────────────────────────────────────────────────────────────────┘
```

- Toggle visibility button to show/hide the key.
- Verify connection button tests the key (spinner + result).
- Finish button enabled only after successful verification (or skipped explicitly).

---

## Global UX Patterns

### Type-to-Filter (all lists)

- Appears as a filter input at top of every scrollable list.
- Fzf-style: matches substring against visible text columns.
- Cleared: shows all items again.
- Applied in: mode picker, file picker, playbook picker, client list, playbook list, past reviews.

### One-Line Descriptions (description bar)

- Every focusable item has a `description` attribute.
- Shown in the persistent description bar at the very bottom of the terminal.
- Examples:

| Item type | Example description |
|-----------|-------------------|
| Mode | "PreCheck — Analyze non-disclosure agreements." |
| Client | "Acme Corporation — 3 reviews, last 2026-07-10." |
| Category | "How long the NDA keeps info confidential." |
| Playbook | "Standard NDA review categories with default positions." |
| Button | "Start a new review from scratch." |
| Tab | "Review — Run a new review or open past results." |

### Empty States

| Screen | Empty message |
|--------|--------------|
| Home (recent reviews) | "No reviews yet. Start one with [+ New review]." |
| Past reviews (filtered) | "No reviews match this filter." |
| Client list | "No clients yet. Add one with [+ Add client]." |
| Playbook list | "No playbooks imported. Import one with [+ Import playbook]." |
| Client detail (reviews) | "No reviews for this client yet." |

### Help System

- `?` opens context-sensitive help overlay.
- Shows global keybindings + tab-specific keys.
- Footer: "Press Esc to close."

---

## Resolved Open Questions (from TUI-Decisions.md)

| Question | Decision | Rationale |
|----------|----------|-----------|
| File picker — show hidden files? | Hide by default. Toggle with Ctrl+H. | Less noise. Ctrl+H is fzf convention. |
| Recent reviews — how many? | 5 | Fits dashboard without scrolling. Configurable later. |
| Gateway config | TUI wizard (step-by-step) | Easier for non-technical users. Panel comes later if requested. |
| Global search (`/`)? | Yes — include in v1 | Navigation power feature. Hits `.` for quick access. |
| Theme toggle? | No — dark mode only for v1 | Standard for terminal apps. Add later if requested. |
| Mouse support? | On by default | Textual default. Scroll and click work. No off switch needed for v1. |
| Status — 1 failing slot, show what? | Full detail (slot + provider + error) | One line is enough; multiple failures → count. |
| Status — gateway indicator clickable? | Yes → opens Settings > Gateway | Fast access to fix failures. |
| Pricing tier in status? | Mark as `—` (em-dash) for v1 | Slot reserved, implementation later. |

---

## Unresolved Open Question

| Question | Context | Status |
|----------|---------|--------|
| Gateway wizard — skip step 1 when launched from "configure slot" shortcut | When user clicks "Configure slot..." on the Gateway settings page and picks a specific slot, the wizard should skip step 1 (slot selection) and start directly at step 2 (provider selection). The user has been asked about this behavior. | **Resolved — always 4 steps.** No skip. User always picks slot first. Simpler, one code path. |
| Multi-slot config with same provider | User may want to use the same provider (e.g. OpenAI) for multiple slots. Avoid re-entering the API key each time. | **Resolved — API key cached per-provider.** `auth.json` already stores keys per provider. Step 4 (key entry) is skipped automatically if the chosen provider already has a key in `auth.json`. User only enters the key once per provider, not once per slot. |

---

## Future Considerations (not in v1 scope)

- Multi-window / split-pane review comparison (dual-party)
- Batch review (multiple docs in one session)
- Real-time collaboration indicators
- Theme toggle (light mode)
- Pro/Enterprise tier upgrades
