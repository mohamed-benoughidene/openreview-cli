# CLI Subcommand Contract: LoanCheck

**Mode name**: `loancheck`
**Spec ref**: Spec 029 FR1
**Playbook file**: `loan-agreement-v1.yaml`
**BUNDLED_PLAYBOOKS key**: `loancheck`
**MODE_VOCABULARY key**: `loancheck`

## Interface

```bash
openreview loancheck <path> [options]
```

`<path>`: Path to a loan agreement/promissory note (PDF or DOCX).

## Options

Same flag set as ASSETCHECK.md. See [ASSETCHECK.md](./ASSETCHECK.md).

## Help text

```
Review a loan agreement/promissory note with LoanCheck.
```

## JSON output mode field

```json
{"mode": "loancheck", ...}
```

## Memo export prefix

`loancheck-`
