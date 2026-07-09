# CLI Subcommand Contract: SettlementCheck (Orphan Unblock)

**Mode name**: `settlementcheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 028)
**Playbook file**: `settlement-agreement-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `settlementcheck` (already exists)
**MODE_VOCABULARY key**: `settlementcheck` (already exists)

## Interface

```bash
openreview settlementcheck <path> [options]
```

`<path>`: Path to a settlement/release agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a settlement/release agreement with SettlementCheck.
```

## Status

Orphan — CLI wiring only.
