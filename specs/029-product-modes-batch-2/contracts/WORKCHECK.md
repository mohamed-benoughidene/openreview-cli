# CLI Subcommand Contract: WorkCheck (Orphan Unblock)

**Mode name**: `workcheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 028)
**Playbook file**: `work-for-hire-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `workcheck` (already exists)
**MODE_VOCABULARY key**: `workcheck` (already exists)

## Interface

```bash
openreview workcheck <path> [options]
```

`<path>`: Path to an independent contractor/work-for-hire agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review an independent contractor/work-for-hire agreement with WorkCheck.
```

## Status

Orphan — CLI wiring only.
