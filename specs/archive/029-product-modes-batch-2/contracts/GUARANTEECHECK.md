# CLI Subcommand Contract: GuaranteeCheck

**Mode name**: `guaranteecheck`
**Spec ref**: Spec 029 FR1
**Playbook file**: `personal-guarantee-v1.yaml`
**BUNDLED_PLAYBOOKS key**: `guaranteecheck`
**MODE_VOCABULARY key**: `guaranteecheck`

## Interface

```bash
openreview guaranteecheck <path> [options]
```

`<path>`: Path to a personal guarantee/suretyship agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a personal guarantee/suretyship agreement with GuaranteeCheck.
```

## JSON output mode field

```json
{"mode": "guaranteecheck", ...}
```

## Memo export prefix

`guaranteecheck-`
