# CLI Subcommand Contract: EngageCheck

**Mode name**: `engagecheck`
**Spec ref**: Spec 029 FR1
**Playbook file**: `engagement-letter-v1.yaml`
**BUNDLED_PLAYBOOKS key**: `engagecheck`
**MODE_VOCABULARY key**: `engagecheck`

## Interface

```bash
openreview engagecheck <path> [options]
```

`<path>`: Path to a professional services engagement letter (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a professional services engagement letter with EngageCheck.
```

## JSON output mode field

```json
{"mode": "engagecheck", ...}
```

## Memo export prefix

`engagecheck-`
