# CLI Subcommand Contract: IndemnityCheck (Orphan Unblock)

**Mode name**: `indemnitycheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 028)
**Playbook file**: `indemnification-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `indemnitycheck` (already exists)
**MODE_VOCABULARY key**: `indemnitycheck` (already exists)

## Interface

```bash
openreview indemnitycheck <path> [options]
```

`<path>`: Path to an indemnification agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review an indemnification agreement with IndemnityCheck.
```

## Status

Orphan — CLI wiring only.
