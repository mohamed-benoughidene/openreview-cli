# CLI Interface Contract — Spec 022 Cleanup & Polish

**Date**: 2026-07-06 | **Spec**: `specs/022-cleanup-polish/spec.md`

## Overview

This contract documents the CLI interface surface under test. No new interfaces are added. Tests validate existing flag behavior, error handling, and output format.

---

## 1. Playbook Flag Conflict

### Affected Commands
All review subcommands: `precheck`, `hirecheck`, `dealcheck` (and any future mode inheriting from `ReviewCommand`).

### Flags
| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--playbook` | `str` | No | Playbook name from registry |
| `--playbook-path` | `Path` | No | Direct path to playbook YAML file |

### Contract
```
WHEN --playbook <NAME> AND --playbook-path <PATH> are both supplied
THEN emit warning to stderr containing both flag names and stating --playbook-path wins
AND continue execution with --playbook-path
AND exit code = 0 (unless other error)
```

### Error Behavior
- No error — warning only, command proceeds
- Warning MUST appear on stderr, not stdout
- Warning MUST contain both `--playbook` and `--playbook-path` flag names
- Warning MUST state which argument is ignored

---

## 2. Bilateral Comparison

### Affected Commands
`openreview compare <doc1> <doc2>` (or equivalent subcommand name).

### Arguments
| Argument | Type | Required | Description |
|----------|------|----------|-------------|
| `doc1` | `Path` | Yes | First document to compare |
| `doc2` | `Path` | Yes | Second document to compare |

### Flags (additional)
| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--output` / `-o` | `Path` | No | Output file path |
| `--format` | `str` | No | Output format (text, json, etc.) |
| `--help` | flag | No | Show help and exit |

### Validation Contract
```
GIVEN invalid input
  doc1 does not exist     → stderr: "not found" + doc1 path, exit != 0
  doc2 does not exist     → stderr: "not found" + doc2 path, exit != 0
  unsupported format      → stderr: format name, exit != 0
  unreadable file         → stderr: "permission" or "unreadable", exit != 0

GIVEN valid input
  both files exist, readable, supported format
  THEN exit = 0
  AND comparison output on stdout or at --output path
```

### Help Output
`openreview compare --help` MUST display:
- Subcommand name (compare or equivalent)
- All arguments and flags listed above
- Brief description of the command

---

## 3. `--no-pii` Flag

### Affected Commands
All review subcommands: `precheck`, `hirecheck`, `dealcheck`, etc.

### Flag
| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--no-pii` | flag | No | Skip PII detection and stripping |

### Contract
```
WHEN --no-pii is present:
  - PiiEngine.detect_all_pages() NOT called
  - Text reaches AI gateway without PII processing
  - Review proceeds normally

WHEN --no-pii is absent (default):
  - PiiEngine.detect_all_pages() IS called
  - Text stripped before AI gateway call
  - Placeholders replace PII entities

ACROSS all review subcommands:
  - Flag MUST be accepted without error
  - --help MUST list the flag
  - Behavior MUST be consistent (inherit from base class)
```

### Help Output
`openreview <subcommand> --help` MUST display `--no-pii` flag in the option list.
