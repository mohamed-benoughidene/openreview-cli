# CLI Subcommand Contract: LicenseCheck (Orphan Unblock)

**Mode name**: `licensecheck`
**Spec ref**: Spec 029 FR2 (orphan from Spec 027)
**Playbook file**: `saas-license-v1.yaml` (existing on disk)
**BUNDLED_PLAYBOOKS key**: `licensecheck` (already exists)
**MODE_VOCABULARY key**: `licensecheck` (already exists)

## Interface

```bash
openreview licensecheck <path> [options]
```

`<path>`: Path to a SaaS/software license agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a SaaS/software license agreement with LicenseCheck.
```

## Status

Orphan — CLI wiring only. Playbook, prompts, BUNDLED_PLAYBOOKS, and MODE_VOCABULARY all pre-exist from Spec 027.
