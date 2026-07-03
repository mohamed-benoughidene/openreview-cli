# CLI Contract: Review Command — Playbook Versioning

**Phase**: 1 — Contracts
**Date**: 2026-07-03

## Command Signature

```text
openreview <mode> review <path> [--playbook <path>] [--playbook-version <semver>] [--no-pii] [--output <format>]
```

**Mode**: `precheck`, `dealcheck`, `hirecheck` (per Q-4 — three modes first)

## Flag: `--playbook-version`

### Purpose
Pin a specific stored playbook version for reproducibility.

### Type
`Optional[str]` — semver string (e.g., `"1.0.0"`, `"1.0.0+1"`)

### Constraints
- REQUIRES `--playbook` flag — standalone usage produces an error
- Must match the semver pattern: `^\d+\.\d+\.\d+(\+\d+)?$`
- Validated against the loaded playbook's `metadata.version` field

### Resolution Order (per FR-7)
1. Load playbook YAML from `--playbook <path>` → extract `id` and embedded `version`
2. Query SQLite `playbook_version` for `(id, --playbook-version)`
3. If found → reuse stored version content (skip further YAML parsing of positions)
4. If not found → compare embedded version against `--playbook-version`
   - Match → store as new version, proceed
   - Mismatch → error

### Error Messages

**Version mismatch** (Scenario 5 Acceptance 2):
```
Error: Requested version 1.0.0 does not match playbook "acme-nda-v2" version 1.1.0
```

**Standalone `--playbook-version` without `--playbook`** (per Q-4):
```
Error: --playbook-version requires --playbook <path>
```

**Invalid semver format**:
```
Error: Invalid version format "abc" — must be semver (e.g., "1.0.0")
```

## Flag Interactions

| `--playbook` | `--playbook-version` | Behavior |
|-------------|---------------------|----------|
| Not specified | Not specified | Auto-detect mode → bundled playbook for the mode |
| Specified | Not specified | Load custom playbook, auto-version (assign 0.1.0 if no version) |
| Specified | Specified | Load → check version match → reuse stored or error |
| Not specified | Specified | **Error** (—playbook-version requires --playbook) |

## Output Format Changes

### ReviewReport JSON (existing schema, `playbook_id` format change)

**Before NX-3**:
```json
{
  "playbook_id": "precheck-nda-v1",
  ...
}
```

**After NX-3**:
```json
{
  "playbook_id": "precheck-nda-v1@1.0.0",
  ...
}
```

The `@` separator is the only change. The prefix before `@` is the playbook ID, unchanged from the existing format.

### Warning Messages (stderr)

**Auto-assigned version** (Scenario 2):
```
Warning: Playbook "<id>" has no version — assigned 0.1.0
```

**Content change without version bump** (Edge Cases):
```
Warning: Playbook "<id>" content changed but version "<ver>" unchanged — storing as <ver>+<N>
```

## Citations

- **§6.4**: 3-position framework flags are implicit (no new CLI flags for position vocabulary — it's a load-time mapping)
- **§6.7**: Single-party only — no bilateral comparison flags
- **Q-7**: Task-level routing — `--playbook-version` is a secondary constraint on the playbook, not a document-type flag
- **Q-8**: G/A/R output — no change to the output schema beyond `playbook_id` format
- **FR-7**: CLI Integration — version flags
