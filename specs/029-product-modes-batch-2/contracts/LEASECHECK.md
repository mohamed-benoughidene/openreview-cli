# CLI Subcommand Contract: LeaseCheck (Orphan Unblock)

**Mode name**: `leasecheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 027)
**Playbook file**: `commercial-lease-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `leasecheck` (already exists)
**MODE_VOCABULARY key**: `leasecheck` (already exists)

## Interface

```bash
openreview leasecheck <path> [options]
```

`<path>`: Path to a commercial lease agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a commercial lease agreement with LeaseCheck.
```

## Status

Orphan — CLI wiring only.
