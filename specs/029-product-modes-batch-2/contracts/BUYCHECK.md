# CLI Subcommand Contract: BuyCheck

**Mode name**: `buycheck`
**Spec ref**: Spec 029 FR1
**Playbook file**: `asset-purchase-v1.yaml`
**BUNDLED_PLAYBOOKS key**: `buycheck`
**MODE_VOCABULARY key**: `buycheck`

## Interface

```bash
openreview buycheck <path> [options]
```

`<path>`: Path to an asset purchase/business acquisition agreement (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review an asset purchase/business acquisition agreement with BuyCheck.
```

## JSON output mode field

```json
{"mode": "buycheck", ...}
```

## Memo export prefix

`buycheck-`
