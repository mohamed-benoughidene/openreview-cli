# CLI Subcommand Contract: LOICheck (Orphan Unblock)

**Mode name**: `loicheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 028)
**Playbook file**: `letter-of-intent-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `loicheck` (already exists)
**MODE_VOCABULARY key**: `loicheck` (already exists)

## Interface

```bash
openreview loicheck <path> [options]
```

`<path>`: Path to a letter of intent or MOU (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a letter of intent or MOU with LOICheck.
```

## Status

Orphan — CLI wiring only.
