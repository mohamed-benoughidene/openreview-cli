# CLI Subcommand Contract: ConsultCheck (Orphan Unblock)

**Mode name**: `consultcheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 028)
**Playbook file**: `consulting-agreement-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `consultcheck` (already exists)
**MODE_VOCABULARY key**: `consultcheck` (already exists)

## Interface

```bash
openreview consultcheck <path> [options]
```

`<path>`: Path to a consulting services agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a consulting services agreement with ConsultCheck.
```

## Status

Orphan — CLI wiring only.
