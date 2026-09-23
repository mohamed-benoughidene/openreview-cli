# CLI and TUI parity matrix

Generated from live source by `scripts/parity/build_parity_matrix.py`. Every row cites a source file and a line number.

- Commit: `8a4d8bf`
- Generated at: 2026-09-23T08:57:43+00:00
- CLI framework: Typer 0.26.7
- TUI framework: Textual 8.2.8
- Python: 3.12.3

Regenerate with:

```bash
uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json
uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json
uv run python scripts/parity/build_parity_matrix.py --cli-json draft/parity/cli-inventory.json --tui-json draft/parity/tui-inventory.json
```

## Summary

| Item | Count |
|---|---|
| CLI inventory rows | 556 |
| TUI inventory rows | 94 |
| Shared call argument rows | 84 |
| Compared shared call argument pairs | 42 |
| Default-value mismatches | 1 |
| Parity join rows | 83 |
| Needs human confirmation | 35 |
| Hidden single-key bindings | 111 |
| Unmatched CLI items | 130 |
| Unmatched TUI items | 49 |
| Semantic collisions | 20 |

## Table A: CLI inventory

| Name | Type | Owner | Flags or actions | Default | Source |
|---|---|---|---|---|---|
| openreview | group |  |  |  | src/openreview_cli/app.py:343 |
| --version | option | openreview | --version | False | src/openreview_cli/app.py:348 |
| --debug | option | openreview | --debug | False | src/openreview_cli/app.py:355 |
| --verbose | option | openreview | --verbose, -v | False | src/openreview_cli/app.py:360 |
| parse | command |  |  |  | src/openreview_cli/app.py:1383 |
| path | argument | parse | path | REQUIRED | src/openreview_cli/app.py:1385 |
| --format | option | parse | --format | text | src/openreview_cli/app.py:1386 |
| --summary | option | parse | --summary | False | src/openreview_cli/app.py:1387 |
| chunk | command |  |  |  | src/openreview_cli/app.py:1801 |
| path | argument | chunk | path | REQUIRED | src/openreview_cli/app.py:1803 |
| --format | option | chunk | --format | text | src/openreview_cli/app.py:1804 |
| --summary | option | chunk | --summary | False | src/openreview_cli/app.py:1805 |
| ingest | command |  |  |  | src/openreview_cli/app.py:2104 |
| file | argument | ingest | file | REQUIRED | src/openreview_cli/app.py:2106 |
| --method | option | ingest | --method | hybrid | src/openreview_cli/app.py:2107 |
| --model | option | ingest | --model | None | src/openreview_cli/app.py:2108 |
| --db-dir | option | ingest | --db-dir | None | src/openreview_cli/app.py:2109 |
| retrieve | command |  |  |  | src/openreview_cli/app.py:2238 |
| query | argument | retrieve | query | REQUIRED | src/openreview_cli/app.py:2240 |
| file | argument | retrieve | file | None | src/openreview_cli/app.py:2242 |
| --method | option | retrieve | --method | None | src/openreview_cli/app.py:2245 |
| --top-k | option | retrieve | --top-k | None | src/openreview_cli/app.py:2247 |
| --rerank | option | retrieve | --rerank | False | src/openreview_cli/app.py:2249 |
| --rerank-depth | option | retrieve | --rerank-depth | None | src/openreview_cli/app.py:2252 |
| --force-rerank | option | retrieve | --force-rerank | False | src/openreview_cli/app.py:2255 |
| --format | option | retrieve | --format | terminal | src/openreview_cli/app.py:2257 |
| --db-dir | option | retrieve | --db-dir | None | src/openreview_cli/app.py:2258 |
| --no-header | option | retrieve | --no-header | False | src/openreview_cli/app.py:2260 |
| index-status | command |  |  |  | src/openreview_cli/app.py:2455 |
| file | argument | index-status | file | None | src/openreview_cli/app.py:2457 |
| --db-dir | option | index-status | --db-dir | None | src/openreview_cli/app.py:2458 |
| index-clear | command |  |  |  | src/openreview_cli/app.py:2512 |
| file | argument | index-clear | file | None | src/openreview_cli/app.py:2514 |
| --all | option | index-clear | --all | False | src/openreview_cli/app.py:2516 |
| --db-dir | option | index-clear | --db-dir | None | src/openreview_cli/app.py:2518 |
| negotiate | command |  |  |  | src/openreview_cli/app.py:2995 |
| doc_path | argument | negotiate | doc_path | REQUIRED | src/openreview_cli/app.py:2997 |
| --playbook-path | option | negotiate | --playbook-path | None | src/openreview_cli/app.py:2999 |
| --solver | option | negotiate | --solver | qre | src/openreview_cli/app.py:3003 |
| --rationality | option | negotiate | --rationality | 1.0 | src/openreview_cli/app.py:3008 |
| --depth | option | negotiate | --depth | 2 | src/openreview_cli/app.py:3013 |
| --weights | option | negotiate | --weights | None | src/openreview_cli/app.py:3018 |
| --confidence-threshold | option | negotiate | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3025 |
| --verbose | option | negotiate | --verbose | False | src/openreview_cli/app.py:3029 |
| --output | option | negotiate | --output | None | src/openreview_cli/app.py:3031 |
| --format | option | negotiate | --format | table | src/openreview_cli/app.py:3033 |
| export | command |  |  |  | src/openreview_cli/app.py:3202 |
| --batch-dir | option | export | --batch-dir | None | src/openreview_cli/app.py:3206 |
| --format | option | export | --format | md | src/openreview_cli/app.py:3209 |
| --output-dir | option | export | --output-dir | review_results | src/openreview_cli/app.py:3211 |
| --mode | option | export | --mode | precheck | src/openreview_cli/app.py:3213 |
| --template | option | export | --template | None | src/openreview_cli/app.py:3216 |
| licensecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | licensecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | licensecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | licensecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | licensecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | licensecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | licensecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | licensecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | licensecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | licensecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | licensecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | licensecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| leasecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | leasecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | leasecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | leasecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | leasecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | leasecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | leasecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | leasecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | leasecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | leasecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | leasecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | leasecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| privacycheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | privacycheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | privacycheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | privacycheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | privacycheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | privacycheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | privacycheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | privacycheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | privacycheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | privacycheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | privacycheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | privacycheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| privacycheck_v2 | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | privacycheck_v2 | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | privacycheck_v2 | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | privacycheck_v2 | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | privacycheck_v2 | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | privacycheck_v2 | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | privacycheck_v2 | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | privacycheck_v2 | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | privacycheck_v2 | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | privacycheck_v2 | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | privacycheck_v2 | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | privacycheck_v2 | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| dealcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | dealcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | dealcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | dealcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | dealcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | dealcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | dealcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | dealcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | dealcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | dealcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | dealcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | dealcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| hirecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | hirecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | hirecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | hirecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | hirecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | hirecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | hirecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | hirecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | hirecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | hirecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | hirecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | hirecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| indemnitycheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | indemnitycheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | indemnitycheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | indemnitycheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | indemnitycheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | indemnitycheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | indemnitycheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | indemnitycheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | indemnitycheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | indemnitycheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | indemnitycheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | indemnitycheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| consultcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | consultcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | consultcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | consultcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | consultcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | consultcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | consultcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | consultcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | consultcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | consultcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | consultcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | consultcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| workcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | workcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | workcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | workcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | workcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | workcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | workcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | workcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | workcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | workcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | workcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | workcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| loicheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | loicheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | loicheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | loicheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | loicheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | loicheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | loicheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | loicheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | loicheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | loicheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | loicheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | loicheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| subcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | subcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | subcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | subcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | subcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | subcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | subcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | subcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | subcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | subcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | subcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | subcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| settlementcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | settlementcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | settlementcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | settlementcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | settlementcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | settlementcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | settlementcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | settlementcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | settlementcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | settlementcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | settlementcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | settlementcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| settlementcheck_v2 | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | settlementcheck_v2 | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | settlementcheck_v2 | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | settlementcheck_v2 | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | settlementcheck_v2 | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | settlementcheck_v2 | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | settlementcheck_v2 | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | settlementcheck_v2 | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | settlementcheck_v2 | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | settlementcheck_v2 | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | settlementcheck_v2 | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | settlementcheck_v2 | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| assetcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | assetcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | assetcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | assetcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | assetcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | assetcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | assetcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | assetcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | assetcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | assetcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | assetcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | assetcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| buycheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | buycheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | buycheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | buycheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | buycheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | buycheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | buycheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | buycheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | buycheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | buycheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | buycheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | buycheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| engagecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | engagecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | engagecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | engagecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | engagecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | engagecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | engagecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | engagecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | engagecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | engagecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | engagecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | engagecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| guaranteecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | guaranteecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | guaranteecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | guaranteecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | guaranteecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | guaranteecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | guaranteecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | guaranteecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | guaranteecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | guaranteecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | guaranteecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | guaranteecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| loancheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | loancheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | loancheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | loancheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | loancheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | loancheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | loancheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | loancheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | loancheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | loancheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | loancheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | loancheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| franchisecheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | franchisecheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | franchisecheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | franchisecheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | franchisecheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | franchisecheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | franchisecheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | franchisecheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | franchisecheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | franchisecheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | franchisecheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | franchisecheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| opcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | opcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | opcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | opcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | opcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | opcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | opcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | opcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | opcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | opcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | opcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | opcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| partnercheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | partnercheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | partnercheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | partnercheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | partnercheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | partnercheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | partnercheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | partnercheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | partnercheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | partnercheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | partnercheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | partnercheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| sponsorcheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | sponsorcheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | sponsorcheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | sponsorcheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | sponsorcheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | sponsorcheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | sponsorcheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | sponsorcheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | sponsorcheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | sponsorcheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | sponsorcheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | sponsorcheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| distrocheck | command |  |  |  | src/openreview_cli/app.py:3287 |
| path | argument | distrocheck | path | REQUIRED | src/openreview_cli/app.py:3289 |
| --allow-partial-pii | option | distrocheck | --allow-partial-pii | False | src/openreview_cli/app.py:3292 |
| --no-pii | option | distrocheck | --no-pii | False | src/openreview_cli/app.py:3295 |
| --playbook | option | distrocheck | --playbook | None | src/openreview_cli/app.py:3297 |
| --format | option | distrocheck | --format | text | src/openreview_cli/app.py:3299 |
| --output | option | distrocheck | --output | None | src/openreview_cli/app.py:3301 |
| --memo-format | option | distrocheck | --memo-format | [] | src/openreview_cli/app.py:3305 |
| --output-dir | option | distrocheck | --output-dir | None | src/openreview_cli/app.py:3310 |
| --verbose | option | distrocheck | --verbose | False | src/openreview_cli/app.py:3313 |
| --confidence-threshold | option | distrocheck | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:3316 |
| --mode-threshold | option | distrocheck | --mode-threshold | [] | src/openreview_cli/app.py:3323 |
| client | group |  |  |  | src/openreview_cli/app.py:383 |
| client add | command | client |  |  | src/openreview_cli/app.py:390 |
| id | argument | client add | id | REQUIRED | src/openreview_cli/app.py:391 |
| name | argument | client add | name | REQUIRED | src/openreview_cli/app.py:391 |
| client list | command | client |  |  | src/openreview_cli/app.py:400 |
| client delete | command | client |  |  | src/openreview_cli/app.py:425 |
| id | argument | client delete | id | REQUIRED | src/openreview_cli/app.py:427 |
| --force | option | client delete | --force | False | src/openreview_cli/app.py:428 |
| config | group |  |  |  | src/openreview_cli/app.py:440 |
| config show | command | config |  |  | src/openreview_cli/app.py:447 |
| config get | command | config |  |  | src/openreview_cli/app.py:472 |
| key | argument | config get | key | REQUIRED | src/openreview_cli/app.py:473 |
| config set | command | config |  |  | src/openreview_cli/app.py:484 |
| key | argument | config set | key | REQUIRED | src/openreview_cli/app.py:485 |
| value | argument | config set | value | REQUIRED | src/openreview_cli/app.py:485 |
| pii | group |  |  |  | src/openreview_cli/app.py:500 |
| pii list | command | pii |  |  | src/openreview_cli/app.py:507 |
| --format | option | pii list | --format | table | src/openreview_cli/app.py:509 |
| --all | option | pii list | --all | False | src/openreview_cli/app.py:510 |
| pii delete | command | pii |  |  | src/openreview_cli/app.py:577 |
| document_hash | argument | pii delete | document_hash | REQUIRED | src/openreview_cli/app.py:579 |
| pii cleanup | command | pii |  |  | src/openreview_cli/app.py:597 |
| --dry-run | option | pii cleanup | --dry-run | False | src/openreview_cli/app.py:599 |
| playbook | group |  |  |  | src/openreview_cli/app.py:628 |
| playbook import | command | playbook |  |  | src/openreview_cli/app.py:635 |
| yaml_path | argument | playbook import | yaml_path | REQUIRED | src/openreview_cli/app.py:637 |
| playbook list | command | playbook |  |  | src/openreview_cli/app.py:676 |
| --include-deleted | option | playbook list | --include-deleted | False | src/openreview_cli/app.py:679 |
| playbook show | command | playbook |  |  | src/openreview_cli/app.py:746 |
| playbook_id | argument | playbook show | playbook_id | REQUIRED | src/openreview_cli/app.py:748 |
| version | argument | playbook show | version | REQUIRED | src/openreview_cli/app.py:749 |
| playbook export | command | playbook |  |  | src/openreview_cli/app.py:832 |
| playbook_id | argument | playbook export | playbook_id | None | src/openreview_cli/app.py:834 |
| --version | option | playbook export | --version | None | src/openreview_cli/app.py:836 |
| --output | option | playbook export | --output | None | src/openreview_cli/app.py:839 |
| --force | option | playbook export | --force | False | src/openreview_cli/app.py:841 |
| --all | option | playbook export | --all | False | src/openreview_cli/app.py:842 |
| playbook diff | command | playbook |  |  | src/openreview_cli/app.py:941 |
| playbook_id | argument | playbook diff | playbook_id | REQUIRED | src/openreview_cli/app.py:943 |
| v1 | argument | playbook diff | v1 | REQUIRED | src/openreview_cli/app.py:944 |
| v2 | argument | playbook diff | v2 | REQUIRED | src/openreview_cli/app.py:945 |
| --json | option | playbook diff | --json | False | src/openreview_cli/app.py:946 |
| playbook set-current | command | playbook |  |  | src/openreview_cli/app.py:1024 |
| playbook_id | argument | playbook set-current | playbook_id | REQUIRED | src/openreview_cli/app.py:1026 |
| version | argument | playbook set-current | version | REQUIRED | src/openreview_cli/app.py:1027 |
| playbook delete | command | playbook |  |  | src/openreview_cli/app.py:1050 |
| playbook_id | argument | playbook delete | playbook_id | None | src/openreview_cli/app.py:1052 |
| --all | option | playbook delete | --all | False | src/openreview_cli/app.py:1053 |
| --force | option | playbook delete | --force | False | src/openreview_cli/app.py:1054 |
| playbook undelete | command | playbook |  |  | src/openreview_cli/app.py:1104 |
| playbook_id | argument | playbook undelete | playbook_id | REQUIRED | src/openreview_cli/app.py:1106 |
| playbook history | command | playbook |  |  | src/openreview_cli/app.py:1143 |
| playbook_id | argument | playbook history | playbook_id | REQUIRED | src/openreview_cli/app.py:1145 |
| precheck | group |  |  |  | src/openreview_cli/app.py:1201 |
| --document | option | precheck | --document, -d | None | src/openreview_cli/app.py:1205 |
| --no-pii | option | precheck | --no-pii | False | src/openreview_cli/app.py:1208 |
| --pii-threshold | option | precheck | --pii-threshold | None | src/openreview_cli/app.py:1212 |
| --output | option | precheck | --output | None | src/openreview_cli/app.py:1217 |
| --format | option | precheck | --format | text | src/openreview_cli/app.py:1219 |
| --force-reprocess | option | precheck | --force-reprocess | False | src/openreview_cli/app.py:1221 |
| precheck review | command | precheck |  |  | src/openreview_cli/app.py:1273 |
| paths | argument | precheck review | paths | REQUIRED | src/openreview_cli/app.py:1276 |
| --playbook-path | option | precheck review | --playbook-path | None | src/openreview_cli/app.py:1279 |
| --playbook | option | precheck review | --playbook | None | src/openreview_cli/app.py:1282 |
| --format | option | precheck review | --format | text | src/openreview_cli/app.py:1284 |
| --output | option | precheck review | --output | None | src/openreview_cli/app.py:1286 |
| --memo-format | option | precheck review | --memo-format | [] | src/openreview_cli/app.py:1290 |
| --output-dir | option | precheck review | --output-dir | None | src/openreview_cli/app.py:1297 |
| --extraction-model | option | precheck review | --extraction-model | None | src/openreview_cli/app.py:1304 |
| --qa-model | option | precheck review | --qa-model | None | src/openreview_cli/app.py:1308 |
| --allow-partial-pii | option | precheck review | --allow-partial-pii | False | src/openreview_cli/app.py:1313 |
| --no-pii | option | precheck review | --no-pii | False | src/openreview_cli/app.py:1316 |
| --verbose | option | precheck review | --verbose | False | src/openreview_cli/app.py:1317 |
| --grounding-mode | option | precheck review | --grounding-mode | strict | src/openreview_cli/app.py:1320 |
| --no-grounding | option | precheck review | --no-grounding | False | src/openreview_cli/app.py:1324 |
| --confidence-threshold | option | precheck review | --confidence-threshold, -ct | 0.7 | src/openreview_cli/app.py:1328 |
| precheck compare | command | precheck |  |  | src/openreview_cli/app.py:1841 |
| doc_a | argument | precheck compare | doc_a | None | src/openreview_cli/app.py:1843 |
| doc_b | argument | precheck compare | doc_b | None | src/openreview_cli/app.py:1844 |
| --extraction-model | option | precheck compare | --extraction-model | None | src/openreview_cli/app.py:1846 |
| --qa-model | option | precheck compare | --qa-model | None | src/openreview_cli/app.py:1850 |
| --comparison-model | option | precheck compare | --comparison-model | None | src/openreview_cli/app.py:1854 |
| --confidence-threshold | option | precheck compare | --confidence-threshold, -ct | None | src/openreview_cli/app.py:1858 |
| --show-redlines | option | precheck compare | --show-redlines | False | src/openreview_cli/app.py:1866 |
| --version-label-a | option | precheck compare | --version-label-a | None | src/openreview_cli/app.py:1869 |
| --version-label-b | option | precheck compare | --version-label-b | None | src/openreview_cli/app.py:1872 |
| --history | option | precheck compare | --history | False | src/openreview_cli/app.py:1875 |
| --format | option | precheck compare | --format | text | src/openreview_cli/app.py:1877 |
| --output | option | precheck compare | --output | None | src/openreview_cli/app.py:1879 |
| --align-only | option | precheck compare | --align-only | False | src/openreview_cli/app.py:1882 |
| --verbose | option | precheck compare | --verbose | False | src/openreview_cli/app.py:1885 |
| --no-pii | option | precheck compare | --no-pii | False | src/openreview_cli/app.py:1887 |
| --allow-partial-pii | option | precheck compare | --allow-partial-pii | False | src/openreview_cli/app.py:1890 |
| --conservative | option | precheck compare | --conservative | False | src/openreview_cli/app.py:1895 |
| --grounding-mode | option | precheck compare | --grounding-mode | strict | src/openreview_cli/app.py:1900 |
| --no-grounding | option | precheck compare | --no-grounding | False | src/openreview_cli/app.py:1904 |
| gateway | group |  |  |  | src/openreview_cli/app.py:1417 |
| gateway setup | command | gateway |  |  | src/openreview_cli/app.py:1430 |
| gateway status | command | gateway |  |  | src/openreview_cli/app.py:1438 |
| gateway providers | command | gateway |  |  | src/openreview_cli/app.py:1460 |
| --json | option | gateway providers | --json | False | src/openreview_cli/app.py:1461 |
| gateway models | command | gateway |  |  | src/openreview_cli/app.py:1508 |
| provider | argument | gateway models | provider | REQUIRED | src/openreview_cli/app.py:1510 |
| --json | option | gateway models | --json | False | src/openreview_cli/app.py:1511 |
| --no-discover | option | gateway models | --no-discover | False | src/openreview_cli/app.py:1513 |
| gateway set | command | gateway |  |  | src/openreview_cli/app.py:1584 |
| slot | argument | gateway set | slot | REQUIRED | src/openreview_cli/app.py:1585 |
| model | argument | gateway set | model | REQUIRED | src/openreview_cli/app.py:1585 |
| gateway fallback | command | gateway |  |  | src/openreview_cli/app.py:1607 |
| slot | argument | gateway fallback | slot | REQUIRED | src/openreview_cli/app.py:1609 |
| model | argument | gateway fallback | model | None | src/openreview_cli/app.py:1611 |
| --clear | option | gateway fallback | --clear | False | src/openreview_cli/app.py:1613 |
| gateway refresh | command | gateway |  |  | src/openreview_cli/app.py:1661 |
| gateway test | command | gateway |  |  | src/openreview_cli/app.py:1672 |
| slot | argument | gateway test | slot | REQUIRED | src/openreview_cli/app.py:1673 |
| gateway costs | command | gateway |  |  | src/openreview_cli/app.py:1707 |
| --today | option | gateway costs | --today | False | src/openreview_cli/app.py:1709 |
| --session | option | gateway costs | --session | None | src/openreview_cli/app.py:1710 |
| gateway provider | group | gateway |  |  | src/openreview_cli/app.py:1423 |
| gateway provider add | command | provider |  |  | src/openreview_cli/app.py:1734 |
| name | argument | gateway provider add | name | REQUIRED | src/openreview_cli/app.py:1736 |
| --base-url | option | gateway provider add | --base-url | None | src/openreview_cli/app.py:1737 |
| --env-key | option | gateway provider add | --env-key | None | src/openreview_cli/app.py:1739 |
| --cred | option | gateway provider add | --cred | None | src/openreview_cli/app.py:1742 |
| --cap-embedding | option | gateway provider add | --cap-embedding | False | src/openreview_cli/app.py:1744 |
| --cap-reasoning | option | gateway provider add | --cap-reasoning | False | src/openreview_cli/app.py:1745 |
| --cap-tool-call | option | gateway provider add | --cap-tool-call | False | src/openreview_cli/app.py:1746 |
| --context-window | option | gateway provider add | --context-window | None | src/openreview_cli/app.py:1748 |
| graph | group |  |  |  | src/openreview_cli/app.py:2637 |
| graph build | command | graph |  |  | src/openreview_cli/app.py:2644 |
| input_path | argument | graph build | input_path | REQUIRED | src/openreview_cli/app.py:2647 |
| --output | option | graph build | --output, -o | None | src/openreview_cli/app.py:2652 |
| --store | option | graph build | --store | False | src/openreview_cli/app.py:2656 |
| --contract-id | option | graph build | --contract-id | None | src/openreview_cli/app.py:2658 |
| --db-path | option | graph build | --db-path | None | src/openreview_cli/app.py:2662 |
| --cluster-clauses | option | graph build | --cluster-clauses | False | src/openreview_cli/app.py:2667 |
| graph metrics | command | graph |  |  | src/openreview_cli/app.py:2710 |
| graph_path | argument | graph metrics | graph_path | None | src/openreview_cli/app.py:2713 |
| --from-db | option | graph metrics | --from-db | False | src/openreview_cli/app.py:2715 |
| --contract-id | option | graph metrics | --contract-id | None | src/openreview_cli/app.py:2717 |
| --db-path | option | graph metrics | --db-path | None | src/openreview_cli/app.py:2721 |
| graph diff | command | graph |  |  | src/openreview_cli/app.py:2770 |
| file_a | argument | graph diff | file_a | REQUIRED | src/openreview_cli/app.py:2772 |
| file_b | argument | graph diff | file_b | REQUIRED | src/openreview_cli/app.py:2773 |
| --json | option | graph diff | --json | False | src/openreview_cli/app.py:2774 |
| graph health | command | graph |  |  | src/openreview_cli/app.py:2853 |
| graph_path | argument | graph health | graph_path | None | src/openreview_cli/app.py:2856 |
| --weights | option | graph health | --weights, -w | None | src/openreview_cli/app.py:2860 |
| --from-db | option | graph health | --from-db | False | src/openreview_cli/app.py:2866 |
| --contract-id | option | graph health | --contract-id | None | src/openreview_cli/app.py:2868 |
| --db-path | option | graph health | --db-path | None | src/openreview_cli/app.py:2872 |
| graph view | command | graph |  |  | src/openreview_cli/app.py:2937 |
| graph_path | argument | graph view | graph_path | None | src/openreview_cli/app.py:2940 |
| --from-db | option | graph view | --from-db | False | src/openreview_cli/app.py:2942 |
| --contract-id | option | graph view | --contract-id | None | src/openreview_cli/app.py:2944 |
| --db-path | option | graph view | --db-path | None | src/openreview_cli/app.py:2948 |
| benchmark | group |  |  |  | src/openreview_cli/benchmark/cli.py:28 |
| benchmark run | command | benchmark |  |  | src/openreview_cli/benchmark/cli.py:56 |
| --datasets | option | benchmark run | --datasets | cuad | src/openreview_cli/benchmark/cli.py:60 |
| --slots | option | benchmark run | --slots | default | src/openreview_cli/benchmark/cli.py:65 |
| --modes | option | benchmark run | --modes | precheck | src/openreview_cli/benchmark/cli.py:70 |
| --prompt-variant | option | benchmark run | --prompt-variant | None | src/openreview_cli/benchmark/cli.py:75 |
| --all | option | benchmark run | --all | False | src/openreview_cli/benchmark/cli.py:80 |
| --ci | option | benchmark run | --ci | False | src/openreview_cli/benchmark/cli.py:85 |
| --compare | option | benchmark run | --compare | None | src/openreview_cli/benchmark/cli.py:90 |
| --save-baseline | option | benchmark run | --save-baseline | False | src/openreview_cli/benchmark/cli.py:95 |
| --download-datasets | option | benchmark run | --download-datasets | False | src/openreview_cli/benchmark/cli.py:100 |
| --memory-watch | option | benchmark run | --memory-watch | False | src/openreview_cli/benchmark/cli.py:105 |
| --multi-party | option | benchmark run | --multi-party | False | src/openreview_cli/benchmark/cli.py:110 |
| --format | option | benchmark run | --format | terminal | src/openreview_cli/benchmark/cli.py:115 |
| --output | option | benchmark run | --output | None | src/openreview_cli/benchmark/cli.py:120 |
| --verbose | option | benchmark run | --verbose | False | src/openreview_cli/benchmark/cli.py:125 |
| --hallucination-method | option | benchmark run | --hallucination-method | lexical | src/openreview_cli/benchmark/cli.py:130 |
| --use-pipeline | option | benchmark run | --use-pipeline | False | src/openreview_cli/benchmark/cli.py:135 |
| --benchmark-tier | option | benchmark run | --benchmark-tier | all | src/openreview_cli/benchmark/cli.py:140 |
| benchmark baseline | command | benchmark |  |  | src/openreview_cli/benchmark/cli.py:352 |
| --modes | option | benchmark baseline | --modes | assetcheck,buycheck,consultcheck,dealcheck,distrocheck,engagecheck,franchisecheck,guaranteecheck,hirecheck,indemnitycheck,leasecheck,licensecheck,loancheck,loicheck,opcheck,partnercheck,precheck,privacycheck,privacycheck_v2,settlementcheck,settlementcheck_v2,sponsorcheck,subcheck,workcheck | src/openreview_cli/benchmark/cli.py:356 |
| --datasets | option | benchmark baseline | --datasets | cuad,maud,contract_nli | src/openreview_cli/benchmark/cli.py:361 |
| --provider | option | benchmark baseline | --provider | mock | src/openreview_cli/benchmark/cli.py:366 |
| --format | option | benchmark baseline | --format | terminal | src/openreview_cli/benchmark/cli.py:371 |
| --output | option | benchmark baseline | --output | None | src/openreview_cli/benchmark/cli.py:376 |
| --save-baseline | option | benchmark baseline | --save-baseline | False | src/openreview_cli/benchmark/cli.py:381 |
| prompt | group |  |  |  | src/openreview_cli/prompts/cli.py:15 |
| prompt create | command | prompt |  |  | src/openreview_cli/prompts/cli.py:34 |
| --name | option | prompt create | --name | None | src/openreview_cli/prompts/cli.py:36 |
| --content | option | prompt create | --content | None | src/openreview_cli/prompts/cli.py:37 |
| --tags | option | prompt create | --tags | None | src/openreview_cli/prompts/cli.py:38 |
| --description | option | prompt create | --description | None | src/openreview_cli/prompts/cli.py:40 |
| prompt update | command | prompt |  |  | src/openreview_cli/prompts/cli.py:56 |
| name | argument | prompt update | name | REQUIRED | src/openreview_cli/prompts/cli.py:58 |
| --content | option | prompt update | --content | None | src/openreview_cli/prompts/cli.py:59 |
| --tags | option | prompt update | --tags | None | src/openreview_cli/prompts/cli.py:60 |
| --description | option | prompt update | --description | None | src/openreview_cli/prompts/cli.py:61 |
| prompt list | command | prompt |  |  | src/openreview_cli/prompts/cli.py:72 |
| --page | option | prompt list | --page | 1 | src/openreview_cli/prompts/cli.py:74 |
| --per-page | option | prompt list | --per-page | 25 | src/openreview_cli/prompts/cli.py:75 |
| prompt show | command | prompt |  |  | src/openreview_cli/prompts/cli.py:88 |
| name | argument | prompt show | name | REQUIRED | src/openreview_cli/prompts/cli.py:90 |
| --version | option | prompt show | --version | None | src/openreview_cli/prompts/cli.py:92 |
| prompt delete | command | prompt |  |  | src/openreview_cli/prompts/cli.py:112 |
| name | argument | prompt delete | name | REQUIRED | src/openreview_cli/prompts/cli.py:114 |
| --force | option | prompt delete | --force | False | src/openreview_cli/prompts/cli.py:115 |
| prompt diff | command | prompt |  |  | src/openreview_cli/prompts/cli.py:127 |
| name | argument | prompt diff | name | REQUIRED | src/openreview_cli/prompts/cli.py:129 |
| --from | option | prompt diff | --from | None | src/openreview_cli/prompts/cli.py:130 |
| --to | option | prompt diff | --to | None | src/openreview_cli/prompts/cli.py:131 |
| prompt bind | command | prompt |  |  | src/openreview_cli/prompts/cli.py:150 |
| --slot | option | prompt bind | --slot | None | src/openreview_cli/prompts/cli.py:152 |
| --prompt | option | prompt bind | --prompt | None | src/openreview_cli/prompts/cli.py:153 |
| --version | option | prompt bind | --version | None | src/openreview_cli/prompts/cli.py:154 |
| prompt unbind | command | prompt |  |  | src/openreview_cli/prompts/cli.py:164 |
| --slot | option | prompt unbind | --slot | None | src/openreview_cli/prompts/cli.py:166 |
| prompt bindings | command | prompt |  |  | src/openreview_cli/prompts/cli.py:176 |
| prompt history | command | prompt |  |  | src/openreview_cli/prompts/cli.py:189 |
| name | argument | prompt history | name | REQUIRED | src/openreview_cli/prompts/cli.py:191 |
| prompt test | command | prompt |  |  | src/openreview_cli/prompts/cli.py:212 |
| --prompt | option | prompt test | --prompt | None | src/openreview_cli/prompts/cli.py:214 |
| --versions | option | prompt test | --versions | None | src/openreview_cli/prompts/cli.py:216 |
| --benchmark | option | prompt test | --benchmark | standard | src/openreview_cli/prompts/cli.py:218 |
| prompt export | command | prompt |  |  | src/openreview_cli/prompts/cli.py:239 |
| name | argument | prompt export | name | None | src/openreview_cli/prompts/cli.py:241 |
| --output | option | prompt export | --output | None | src/openreview_cli/prompts/cli.py:242 |
| prompt import | command | prompt |  |  | src/openreview_cli/prompts/cli.py:260 |
| path | argument | prompt import | path | REQUIRED | src/openreview_cli/prompts/cli.py:262 |
| prompt optimize | command | prompt |  |  | src/openreview_cli/prompts/cli.py:287 |
| --prompt | option | prompt optimize | --prompt | None | src/openreview_cli/prompts/cli.py:289 |
| --benchmark | option | prompt optimize | --benchmark | standard | src/openreview_cli/prompts/cli.py:290 |
| --iterations | option | prompt optimize | --iterations | 5 | src/openreview_cli/prompts/cli.py:291 |

## Table B: TUI inventory

| Name | Type | Owner | Flags or actions | Default | Source |
|---|---|---|---|---|---|
| OpenReviewApp | app | openreview_cli.tui.app |  |  | src/openreview_cli/tui/app.py:18 |
| ctrl+c | binding | OpenReviewApp | ctrl+c, quit_or_warn, Quit |  | src/openreview_cli/tui/app.py:25 |
| 1 | binding | OpenReviewApp | 1, show_tab('home'), Home |  | src/openreview_cli/tui/app.py:26 |
| 2 | binding | OpenReviewApp | 2, show_tab('review'), Review |  | src/openreview_cli/tui/app.py:27 |
| 3 | binding | OpenReviewApp | 3, show_tab('clients'), Clients |  | src/openreview_cli/tui/app.py:28 |
| 4 | binding | OpenReviewApp | 4, show_tab('playbooks'), Playbooks |  | src/openreview_cli/tui/app.py:29 |
| 5 | binding | OpenReviewApp | 5, show_tab('settings'), Settings |  | src/openreview_cli/tui/app.py:30 |
| / | binding | OpenReviewApp | /, open_search, Search |  | src/openreview_cli/tui/app.py:31 |
| action_show_tab | action | OpenReviewApp | 1, 2, 3, 4, 5 |  | src/openreview_cli/tui/app.py:68 |
| action_quit_or_warn | action | OpenReviewApp | ctrl+c |  | src/openreview_cli/tui/app.py:72 |
| action_open_search | action | OpenReviewApp | / |  | src/openreview_cli/tui/app.py:118 |
| _ctrl_c_warned | default-state | OpenReviewApp | _ctrl_c_warned | False | src/openreview_cli/tui/app.py:36 |
| AnnotateModal | screen | openreview_cli.tui.screens.amber_queue |  |  | src/openreview_cli/tui/screens/amber_queue.py:54 |
| escape | binding | AnnotateModal | escape, cancel, Cancel |  | src/openreview_cli/tui/screens/amber_queue.py:68 |
| action_cancel | action | AnnotateModal | escape |  | src/openreview_cli/tui/screens/amber_queue.py:87 |
| AmberQueueScreen | screen | openreview_cli.tui.screens.amber_queue |  |  | src/openreview_cli/tui/screens/amber_queue.py:100 |
| a | binding | AmberQueueScreen | a, accept, Accept |  | src/openreview_cli/tui/screens/amber_queue.py:116 |
| r | binding | AmberQueueScreen | r, reject, Reject |  | src/openreview_cli/tui/screens/amber_queue.py:117 |
| n | binding | AmberQueueScreen | n, annotate, Note |  | src/openreview_cli/tui/screens/amber_queue.py:118 |
| s | binding | AmberQueueScreen | s, next, Next |  | src/openreview_cli/tui/screens/amber_queue.py:119 |
| j | binding | AmberQueueScreen | j, next, Next |  | src/openreview_cli/tui/screens/amber_queue.py:120 |
| down | binding | AmberQueueScreen | down, next, Next |  | src/openreview_cli/tui/screens/amber_queue.py:121 |
| k | binding | AmberQueueScreen | k, previous, Previous |  | src/openreview_cli/tui/screens/amber_queue.py:122 |
| up | binding | AmberQueueScreen | up, previous, Previous |  | src/openreview_cli/tui/screens/amber_queue.py:123 |
| t | binding | AmberQueueScreen | t, toggle_overview, Overview |  | src/openreview_cli/tui/screens/amber_queue.py:124 |
| o | binding | AmberQueueScreen | o, toggle_overview, Overview |  | src/openreview_cli/tui/screens/amber_queue.py:125 |
| escape | binding | AmberQueueScreen | escape, close, Done |  | src/openreview_cli/tui/screens/amber_queue.py:126 |
| q | binding | AmberQueueScreen | q, close, Done |  | src/openreview_cli/tui/screens/amber_queue.py:127 |
| action_accept | action | AmberQueueScreen | a |  | src/openreview_cli/tui/screens/amber_queue.py:228 |
| action_reject | action | AmberQueueScreen | r |  | src/openreview_cli/tui/screens/amber_queue.py:231 |
| action_next | action | AmberQueueScreen | s, j, down |  | src/openreview_cli/tui/screens/amber_queue.py:234 |
| action_previous | action | AmberQueueScreen | k, up |  | src/openreview_cli/tui/screens/amber_queue.py:237 |
| action_toggle_overview | action | AmberQueueScreen | t, o |  | src/openreview_cli/tui/screens/amber_queue.py:240 |
| action_annotate | action | AmberQueueScreen | n |  | src/openreview_cli/tui/screens/amber_queue.py:244 |
| action_close | action | AmberQueueScreen | escape, q |  | src/openreview_cli/tui/screens/amber_queue.py:250 |
| _index | default-state | AmberQueueScreen | _index | 0 | src/openreview_cli/tui/screens/amber_queue.py:133 |
| _overview | default-state | AmberQueueScreen | _overview | False | src/openreview_cli/tui/screens/amber_queue.py:134 |
| ClientDetailScreen | screen | openreview_cli.tui.screens.client_detail |  |  | src/openreview_cli/tui/screens/client_detail.py:13 |
| escape | binding | ClientDetailScreen | escape, pop_screen, Back |  | src/openreview_cli/tui/screens/client_detail.py:27 |
| action_pop_screen | action | ClientDetailScreen | escape |  | src/openreview_cli/tui/screens/client_detail.py:98 |
| ClientForm | screen | openreview_cli.tui.screens.client_form |  |  | src/openreview_cli/tui/screens/client_form.py:13 |
| ConfirmModal | screen | openreview_cli.tui.screens.confirm |  |  | src/openreview_cli/tui/screens/confirm.py:13 |
| DatabaseErrorScreen | screen | openreview_cli.tui.screens.db_error |  |  | src/openreview_cli/tui/screens/db_error.py:15 |
| EgressReviewModal | screen | openreview_cli.tui.screens.egress_review |  |  | src/openreview_cli/tui/screens/egress_review.py:16 |
| escape | binding | EgressReviewModal | escape, cancel, Cancel |  | src/openreview_cli/tui/screens/egress_review.py:31 |
| c | binding | EgressReviewModal | c, confirm, Continue |  | src/openreview_cli/tui/screens/egress_review.py:32 |
| action_confirm | action | EgressReviewModal | c |  | src/openreview_cli/tui/screens/egress_review.py:53 |
| action_cancel | action | EgressReviewModal | escape |  | src/openreview_cli/tui/screens/egress_review.py:56 |
| GatewayWizard | screen | openreview_cli.tui.screens.gateway_wizard |  |  | src/openreview_cli/tui/screens/gateway_wizard.py:30 |
| NegotiationProgressScreen | screen | openreview_cli.tui.screens.negotiation_progress |  |  | src/openreview_cli/tui/screens/negotiation_progress.py:16 |
| NegotiationResultScreen | screen | openreview_cli.tui.screens.negotiation_result |  |  | src/openreview_cli/tui/screens/negotiation_result.py:19 |
| escape | binding | NegotiationResultScreen | escape, close, Close |  | src/openreview_cli/tui/screens/negotiation_result.py:32 |
| action_close | action | NegotiationResultScreen | escape |  | src/openreview_cli/tui/screens/negotiation_result.py:71 |
| NegotiationWizard | screen | openreview_cli.tui.screens.negotiation_wizard |  |  | src/openreview_cli/tui/screens/negotiation_wizard.py:66 |
| escape | binding | NegotiationWizard | escape, cancel_wizard, Cancel |  | src/openreview_cli/tui/screens/negotiation_wizard.py:81 |
| ctrl+h | binding | NegotiationWizard | ctrl+h, toggle_hidden, Hidden files |  | src/openreview_cli/tui/screens/negotiation_wizard.py:82 |
| action_toggle_hidden | action | NegotiationWizard | ctrl+h |  | src/openreview_cli/tui/screens/negotiation_wizard.py:137 |
| action_cancel_wizard | action | NegotiationWizard | escape |  | src/openreview_cli/tui/screens/negotiation_wizard.py:180 |
| _step | default-state | NegotiationWizard | _step | 1 | src/openreview_cli/tui/screens/negotiation_wizard.py:87 |
| PlaybookDetailScreen | screen | openreview_cli.tui.screens.playbook_detail |  |  | src/openreview_cli/tui/screens/playbook_detail.py:40 |
| VersionHistoryScreen | screen | openreview_cli.tui.screens.playbook_detail |  |  | src/openreview_cli/tui/screens/playbook_detail.py:166 |
| VersionDiffScreen | screen | openreview_cli.tui.screens.playbook_detail |  |  | src/openreview_cli/tui/screens/playbook_detail.py:243 |
| ProgressScreen | screen | openreview_cli.tui.screens.progress |  |  | src/openreview_cli/tui/screens/progress.py:45 |
| ResultScreen | screen | openreview_cli.tui.screens.result |  |  | src/openreview_cli/tui/screens/result.py:34 |
| l | binding | ResultScreen | l, toggle_layout, Toggle layout |  | src/openreview_cli/tui/screens/result.py:52 |
| t | binding | ResultScreen | t, open_amber_queue, Triage |  | src/openreview_cli/tui/screens/result.py:53 |
| m | binding | ResultScreen | m, open_amber_queue, Amber queue |  | src/openreview_cli/tui/screens/result.py:54 |
| ] | binding | ResultScreen | ], next_doc, Next document |  | src/openreview_cli/tui/screens/result.py:55 |
| [ | binding | ResultScreen | [, prev_doc, Prev document |  | src/openreview_cli/tui/screens/result.py:56 |
| right | binding | ResultScreen | right, next_page, Next page |  | src/openreview_cli/tui/screens/result.py:57 |
| left | binding | ResultScreen | left, prev_page, Prev page |  | src/openreview_cli/tui/screens/result.py:58 |
| escape | binding | ResultScreen | escape, close, Close |  | src/openreview_cli/tui/screens/result.py:59 |
| action_toggle_layout | action | ResultScreen | l |  | src/openreview_cli/tui/screens/result.py:264 |
| action_close | action | ResultScreen | escape |  | src/openreview_cli/tui/screens/result.py:274 |
| action_open_amber_queue | action | ResultScreen | t, m |  | src/openreview_cli/tui/screens/result.py:277 |
| action_next_page | action | ResultScreen | right |  | src/openreview_cli/tui/screens/result.py:304 |
| action_prev_page | action | ResultScreen | left |  | src/openreview_cli/tui/screens/result.py:312 |
| action_next_doc | action | ResultScreen | ] |  | src/openreview_cli/tui/screens/result.py:318 |
| action_prev_doc | action | ResultScreen | [ |  | src/openreview_cli/tui/screens/result.py:325 |
| _layout_split | default-state | ResultScreen | _layout_split | True | src/openreview_cli/tui/screens/result.py:72 |
| ReviewWizard | screen | openreview_cli.tui.screens.review_wizard |  |  | src/openreview_cli/tui/screens/review_wizard.py:67 |
| escape | binding | ReviewWizard | escape, cancel_wizard, Cancel |  | src/openreview_cli/tui/screens/review_wizard.py:82 |
| ctrl+h | binding | ReviewWizard | ctrl+h, toggle_hidden, Hidden files |  | src/openreview_cli/tui/screens/review_wizard.py:83 |
| action_toggle_hidden | action | ReviewWizard | ctrl+h |  | src/openreview_cli/tui/screens/review_wizard.py:280 |
| action_cancel_wizard | action | ReviewWizard | escape |  | src/openreview_cli/tui/screens/review_wizard.py:287 |
| _step | default-state | ReviewWizard | _step | 1 | src/openreview_cli/tui/screens/review_wizard.py:88 |
| _disable_pii | default-state | ReviewWizard | _disable_pii | False | src/openreview_cli/tui/screens/review_wizard.py:92 |
| _mode_filter_text | default-state | ReviewWizard | _mode_filter_text | "" | src/openreview_cli/tui/screens/review_wizard.py:94 |
| Checkbox.value | default-state | ReviewWizard | value | False | src/openreview_cli/tui/screens/review_wizard.py:234 |
| Checkbox.value | default-state | ReviewWizard | value | False | src/openreview_cli/tui/screens/review_wizard.py:238 |
| SearchScreen | screen | openreview_cli.tui.screens.search |  |  | src/openreview_cli/tui/screens/search.py:31 |
| escape | binding | SearchScreen | escape, close, Close |  | src/openreview_cli/tui/screens/search.py:43 |
| action_close | action | SearchScreen | escape |  | src/openreview_cli/tui/screens/search.py:106 |
| _ImportModal | screen | openreview_cli.tui.tabs.playbooks |  |  | src/openreview_cli/tui/tabs/playbooks.py:141 |

## Table C: parity join

| Match | CLI item | CLI source | TUI item | TUI source | Default mismatch |
|---|---|---|---|---|---|
| MISMATCH-ABSENT | --grounding-mode (precheck review) | src/openreview_cli/app.py:1364 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | strict (CLI src/openreview_cli/app.py:1364) vs NOT PASSED (TUI src/openreview_cli/tui/domain/review.py:50) |
| SHARED-CALL | --align-only (precheck compare) | src/openreview_cli/app.py:1977 | no TUI control for align_only | (none) | none |
| SHARED-CALL | --allow-partial-pii (precheck compare) | src/openreview_cli/app.py:1974 | no TUI control for allow_partial_pii | (none) | none |
| SHARED-CALL | --allow-partial-pii (precheck review) | src/openreview_cli/app.py:1367 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | --comparison-model (precheck compare) | src/openreview_cli/app.py:1979 | no TUI control for comparison_model | (none) | none |
| SHARED-CALL | --confidence-threshold (precheck compare) | src/openreview_cli/app.py:1976 | no TUI control for confidence_threshold | (none) | none |
| SHARED-CALL | --confidence-threshold (precheck review) | src/openreview_cli/app.py:1365 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:58 | none |
| SHARED-CALL | --extraction-model (precheck compare) | src/openreview_cli/app.py:1971 | no TUI control for extraction_model | (none) | none |
| SHARED-CALL | --extraction-model (precheck review) | src/openreview_cli/app.py:1360 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:54 | none |
| SHARED-CALL | --grounding-mode (precheck compare) | src/openreview_cli/app.py:1978 | no TUI control for grounding_mode | (none) | none |
| SHARED-CALL | --no-pii (precheck compare) | src/openreview_cli/app.py:1973 | no TUI control for no_pii | (none) | none |
| SHARED-CALL | --no-pii (precheck review) | src/openreview_cli/app.py:1362 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:56 | none |
| SHARED-CALL | --playbook-path (precheck review) | src/openreview_cli/app.py:1358 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:52 | none |
| SHARED-CALL | --verbose (precheck compare) | src/openreview_cli/app.py:1975 | no TUI control for verbose | (none) | none |
| SHARED-CALL | --verbose (precheck review) | src/openreview_cli/app.py:1363 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:57 | none |
| SHARED-CALL | --version-label-a (precheck compare) | src/openreview_cli/app.py:1980 | no TUI control for version_label_a | (none) | none |
| SHARED-CALL | --version-label-b (precheck compare) | src/openreview_cli/app.py:1981 | no TUI control for version_label_b | (none) | none |
| SHARED-CALL | precheck compare (doc_a_path) | src/openreview_cli/app.py:1968 | no TUI control for doc_a_path | (none) | none |
| SHARED-CALL | precheck compare (doc_b_path) | src/openreview_cli/app.py:1969 | no TUI control for doc_b_path | (none) | none |
| SHARED-CALL | precheck compare (playbook) | src/openreview_cli/app.py:1970 | no TUI control for playbook | (none) | none |
| SHARED-CALL | precheck compare (qa_model) | src/openreview_cli/app.py:1972 | no TUI control for qa_model | (none) | none |
| SHARED-CALL | precheck review (mode) | src/openreview_cli/app.py:1366 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:59 | none |
| SHARED-CALL | precheck review (mode_threshold_overrides) | src/openreview_cli/app.py:1356 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | precheck review (paths) | src/openreview_cli/app.py:1357 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:51 | none |
| SHARED-CALL | precheck review (playbook_id) | src/openreview_cli/app.py:1359 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:53 | none |
| SHARED-CALL | precheck review (progress_callback) | src/openreview_cli/app.py:1356 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:60 | none |
| SHARED-CALL | precheck review (qa_model) | src/openreview_cli/app.py:1361 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:55 | none |
| SHARED-CALL | precheck review (session_id) | src/openreview_cli/app.py:1356 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | product modes (allow_partial_pii) | src/openreview_cli/app.py:3431 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | product modes (confidence_threshold) | src/openreview_cli/app.py:3428 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:58 | none |
| SHARED-CALL | product modes (extraction_model) | src/openreview_cli/app.py:3424 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:54 | none |
| SHARED-CALL | product modes (grounding_mode) | src/openreview_cli/app.py:3421 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | product modes (mode) | src/openreview_cli/app.py:3430 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:59 | none |
| SHARED-CALL | product modes (mode_threshold_overrides) | src/openreview_cli/app.py:3429 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | product modes (no_pii) | src/openreview_cli/app.py:3426 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:56 | none |
| SHARED-CALL | product modes (paths) | src/openreview_cli/app.py:3422 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:51 | none |
| SHARED-CALL | product modes (playbook_id) | src/openreview_cli/app.py:3421 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:53 | none |
| SHARED-CALL | product modes (playbook_path) | src/openreview_cli/app.py:3423 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:52 | none |
| SHARED-CALL | product modes (progress_callback) | src/openreview_cli/app.py:3421 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:60 | none |
| SHARED-CALL | product modes (qa_model) | src/openreview_cli/app.py:3425 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:55 | none |
| SHARED-CALL | product modes (session_id) | src/openreview_cli/app.py:3421 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:50 | none |
| SHARED-CALL | product modes (verbose) | src/openreview_cli/app.py:3427 | openreview_cli.tui.domain.review.run_review_via_tui | src/openreview_cli/tui/domain/review.py:57 | none |
| CERTAIN | --playbook (option) | src/openreview_cli/app.py:3297 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | --playbook (option) | src/openreview_cli/app.py:1282 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | --playbook-path (option) | src/openreview_cli/app.py:2999 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | --playbook-path (option) | src/openreview_cli/app.py:1279 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | client add (command) | src/openreview_cli/app.py:390 | ClientDetailScreen (screen) | src/openreview_cli/tui/screens/client_detail.py:13 | none |
| CERTAIN | client add (command) | src/openreview_cli/app.py:390 | ClientForm (screen) | src/openreview_cli/tui/screens/client_form.py:13 | none |
| CERTAIN | client delete (command) | src/openreview_cli/app.py:425 | ClientDetailScreen (screen) | src/openreview_cli/tui/screens/client_detail.py:13 | none |
| CERTAIN | client delete (command) | src/openreview_cli/app.py:425 | ClientForm (screen) | src/openreview_cli/tui/screens/client_form.py:13 | none |
| CERTAIN | client list (command) | src/openreview_cli/app.py:400 | ClientDetailScreen (screen) | src/openreview_cli/tui/screens/client_detail.py:13 | none |
| CERTAIN | client list (command) | src/openreview_cli/app.py:400 | ClientForm (screen) | src/openreview_cli/tui/screens/client_form.py:13 | none |
| CERTAIN | gateway costs (command) | src/openreview_cli/app.py:1707 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway fallback (command) | src/openreview_cli/app.py:1607 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway models (command) | src/openreview_cli/app.py:1508 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway provider add (command) | src/openreview_cli/app.py:1734 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway providers (command) | src/openreview_cli/app.py:1460 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway refresh (command) | src/openreview_cli/app.py:1661 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway set (command) | src/openreview_cli/app.py:1584 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway setup (command) | src/openreview_cli/app.py:1430 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway status (command) | src/openreview_cli/app.py:1438 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | gateway test (command) | src/openreview_cli/app.py:1672 | GatewayWizard (screen) | src/openreview_cli/tui/screens/gateway_wizard.py:30 | none |
| CERTAIN | graph diff (command) | src/openreview_cli/app.py:2770 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | none |
| CERTAIN | playbook delete (command) | src/openreview_cli/app.py:1050 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook diff (command) | src/openreview_cli/app.py:941 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook diff (command) | src/openreview_cli/app.py:941 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | none |
| CERTAIN | playbook export (command) | src/openreview_cli/app.py:832 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook history (command) | src/openreview_cli/app.py:1143 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook import (command) | src/openreview_cli/app.py:635 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook import (command) | src/openreview_cli/app.py:635 | _ImportModal (screen) | src/openreview_cli/tui/tabs/playbooks.py:141 | none |
| CERTAIN | playbook list (command) | src/openreview_cli/app.py:676 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook set-current (command) | src/openreview_cli/app.py:1024 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook show (command) | src/openreview_cli/app.py:746 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook undelete (command) | src/openreview_cli/app.py:1104 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook_id (argument) | src/openreview_cli/app.py:748 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook_id (argument) | src/openreview_cli/app.py:834 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook_id (argument) | src/openreview_cli/app.py:943 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | playbook_id (argument) | src/openreview_cli/app.py:1106 | PlaybookDetailScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:40 | none |
| CERTAIN | precheck review (command) | src/openreview_cli/app.py:1273 | EgressReviewModal (screen) | src/openreview_cli/tui/screens/egress_review.py:16 | none |
| CERTAIN | precheck review (command) | src/openreview_cli/app.py:1273 | OpenReviewApp (app) | src/openreview_cli/tui/app.py:18 | none |
| CERTAIN | precheck review (command) | src/openreview_cli/app.py:1273 | ReviewWizard (screen) | src/openreview_cli/tui/screens/review_wizard.py:67 | none |
| CERTAIN | prompt diff (command) | src/openreview_cli/prompts/cli.py:127 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | none |
| CERTAIN | prompt import (command) | src/openreview_cli/prompts/cli.py:260 | _ImportModal (screen) | src/openreview_cli/tui/tabs/playbooks.py:141 | none |

## Default-value mismatches

- `run_review.grounding_mode` (MISMATCH-ABSENT): CLI `strict` at src/openreview_cli/app.py:1364 (precheck review) against TUI `NOT PASSED` at src/openreview_cli/tui/domain/review.py:50 (openreview_cli.tui.domain.review.run_review_via_tui). Callee default: `None`.

## Shared call sites without a counterpart

- `run_comparison.doc_a_path`: no TUI call site
- `run_comparison.doc_b_path`: no TUI call site
- `run_comparison.playbook`: no TUI call site
- `run_comparison.extraction_model`: no TUI call site
- `run_comparison.qa_model`: no TUI call site
- `run_comparison.no_pii`: no TUI call site
- `run_comparison.allow_partial_pii`: no TUI call site
- `run_comparison.verbose`: no TUI call site
- `run_comparison.confidence_threshold`: no TUI call site
- `run_comparison.align_only`: no TUI call site
- `run_comparison.grounding_mode`: no TUI call site
- `run_comparison.comparison_model`: no TUI call site
- `run_comparison.version_label_a`: no TUI call site
- `run_comparison.version_label_b`: no TUI call site

## Unresolved shared call arguments

- `run_review.paths`: CLI `REQUIRED` (src/openreview_cli/app.py:1357) against TUI `paths` (src/openreview_cli/tui/domain/review.py:51).
- `run_review.paths`: CLI `[path]` (src/openreview_cli/app.py:3422) against TUI `paths` (src/openreview_cli/tui/domain/review.py:51).
- `run_review.playbook_path`: CLI `resolved_playbook_path` (src/openreview_cli/app.py:3423) against TUI `None` (src/openreview_cli/tui/domain/review.py:52).
- `run_review.extraction_model`: CLI `extraction_model or 'extraction'` (src/openreview_cli/app.py:1360) against TUI `extraction` (src/openreview_cli/tui/domain/review.py:54).
- `run_review.no_pii`: CLI `no_pii` (src/openreview_cli/app.py:3426) against TUI `False` (src/openreview_cli/tui/domain/review.py:56).
- `run_review.mode_threshold_overrides`: CLI `mode_threshold_overrides` (src/openreview_cli/app.py:3429) against TUI `NOT PASSED` (src/openreview_cli/tui/domain/review.py:50).
- `run_review.mode`: CLI `mode` (src/openreview_cli/app.py:3430) against TUI `precheck` (src/openreview_cli/tui/domain/review.py:59).

## Needs human confirmation

Grouped by the TUI screen each CLI item points at. 111 single and double character keybinding rows are omitted.

### OpenReviewApp

| CLI item | CLI source | TUI item | TUI source | Shared token | Reason |
|---|---|---|---|---|---|
| config show (command) | src/openreview_cli/app.py:447 | action_show_tab (action) | src/openreview_cli/tui/app.py:68 | show | generic token only: show |
| playbook show (command) | src/openreview_cli/app.py:746 | action_show_tab (action) | src/openreview_cli/tui/app.py:68 | show | generic token only: show |
| --show-redlines (option) | src/openreview_cli/app.py:1866 | action_show_tab (action) | src/openreview_cli/tui/app.py:68 | show | generic token only: show |
| prompt show (command) | src/openreview_cli/prompts/cli.py:88 | action_show_tab (action) | src/openreview_cli/tui/app.py:68 | show | generic token only: show |

### ResultScreen

| CLI item | CLI source | TUI item | TUI source | Shared token | Reason |
|---|---|---|---|---|---|
| doc_path (argument) | src/openreview_cli/app.py:2997 | action_next_doc (action) | src/openreview_cli/tui/screens/result.py:318 | doc | generic token only: doc |
| doc_path (argument) | src/openreview_cli/app.py:2997 | action_prev_doc (action) | src/openreview_cli/tui/screens/result.py:325 | doc | generic token only: doc |
| doc_a (argument) | src/openreview_cli/app.py:1843 | action_next_doc (action) | src/openreview_cli/tui/screens/result.py:318 | doc | generic token only: doc |
| doc_a (argument) | src/openreview_cli/app.py:1843 | action_prev_doc (action) | src/openreview_cli/tui/screens/result.py:325 | doc | generic token only: doc |
| doc_b (argument) | src/openreview_cli/app.py:1844 | action_next_doc (action) | src/openreview_cli/tui/screens/result.py:318 | doc | generic token only: doc |
| doc_b (argument) | src/openreview_cli/app.py:1844 | action_prev_doc (action) | src/openreview_cli/tui/screens/result.py:325 | doc | generic token only: doc |
| --page (option) | src/openreview_cli/prompts/cli.py:74 | action_next_page (action) | src/openreview_cli/tui/screens/result.py:304 | page | generic token only: page |
| --page (option) | src/openreview_cli/prompts/cli.py:74 | action_prev_page (action) | src/openreview_cli/tui/screens/result.py:312 | page | generic token only: page |
| --per-page (option) | src/openreview_cli/prompts/cli.py:75 | action_next_page (action) | src/openreview_cli/tui/screens/result.py:304 | page | generic token only: page |
| --per-page (option) | src/openreview_cli/prompts/cli.py:75 | action_prev_page (action) | src/openreview_cli/tui/screens/result.py:312 | page | generic token only: page |

### VersionDiffScreen

| CLI item | CLI source | TUI item | TUI source | Shared token | Reason |
|---|---|---|---|---|---|
| --version (option) | src/openreview_cli/app.py:348; src/openreview_cli/app.py:836; src/openreview_cli/prompts/cli.py:154; src/openreview_cli/prompts/cli.py:92 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | version | generic token only: version |
| version (argument) | src/openreview_cli/app.py:1027; src/openreview_cli/app.py:749 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | version | generic token only: version |
| --version-label-a (option) | src/openreview_cli/app.py:1869 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | version | generic token only: version |
| --version-label-b (option) | src/openreview_cli/app.py:1872 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | version | generic token only: version |
| --versions (option) | src/openreview_cli/prompts/cli.py:216 | VersionDiffScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:243 | version | generic token only: version |

### VersionHistoryScreen

| CLI item | CLI source | TUI item | TUI source | Shared token | Reason |
|---|---|---|---|---|---|
| --version (option) | src/openreview_cli/app.py:348; src/openreview_cli/app.py:836; src/openreview_cli/prompts/cli.py:154; src/openreview_cli/prompts/cli.py:92 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | version | generic token only: version |
| version (argument) | src/openreview_cli/app.py:1027; src/openreview_cli/app.py:749 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | version | generic token only: version |
| playbook history (command) | src/openreview_cli/app.py:1143 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | history | generic token only: history |
| --version-label-a (option) | src/openreview_cli/app.py:1869 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | version | generic token only: version |
| --version-label-b (option) | src/openreview_cli/app.py:1872 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | version | generic token only: version |
| --history (option) | src/openreview_cli/app.py:1875 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | history | generic token only: history |
| prompt history (command) | src/openreview_cli/prompts/cli.py:189 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | history | generic token only: history |
| --versions (option) | src/openreview_cli/prompts/cli.py:216 | VersionHistoryScreen (screen) | src/openreview_cli/tui/screens/playbook_detail.py:166 | version | generic token only: version |


## Unmatched CLI items

| Item | Type | Owner | Source |
|---|---|---|---|
| --debug | option | openreview | src/openreview_cli/app.py:355 |
| --verbose | option | openreview | src/openreview_cli/app.py:360 |
| parse | command |  | src/openreview_cli/app.py:1383 |
| --format | option | parse, chunk | src/openreview_cli/app.py:1386 |
| --summary | option | parse, chunk | src/openreview_cli/app.py:1387 |
| chunk | command |  | src/openreview_cli/app.py:1801 |
| ingest | command |  | src/openreview_cli/app.py:2104 |
| --method | option | ingest | src/openreview_cli/app.py:2107 |
| --model | option | ingest | src/openreview_cli/app.py:2108 |
| --db-dir | option | ingest, retrieve, +2 more | src/openreview_cli/app.py:2109 |
| query | argument | retrieve | src/openreview_cli/app.py:2240 |
| --method | option | retrieve | src/openreview_cli/app.py:2245 |
| --rerank | option | retrieve | src/openreview_cli/app.py:2249 |
| --rerank-depth | option | retrieve | src/openreview_cli/app.py:2252 |
| --force-rerank | option | retrieve | src/openreview_cli/app.py:2255 |
| --format | option | retrieve | src/openreview_cli/app.py:2257 |
| --no-header | option | retrieve | src/openreview_cli/app.py:2260 |
| --solver | option | negotiate | src/openreview_cli/app.py:3003 |
| --rationality | option | negotiate | src/openreview_cli/app.py:3008 |
| --depth | option | negotiate | src/openreview_cli/app.py:3013 |
| --weights | option | negotiate | src/openreview_cli/app.py:3018 |
| --verbose | option | negotiate, licensecheck, +23 more | src/openreview_cli/app.py:3029 |
| --format | option | negotiate | src/openreview_cli/app.py:3033 |
| --format | option | export | src/openreview_cli/app.py:3209 |
| --mode | option | export | src/openreview_cli/app.py:3213 |
| --template | option | export | src/openreview_cli/app.py:3216 |
| --format | option | licensecheck, leasecheck, +22 more | src/openreview_cli/app.py:3299 |
| --mode-threshold | option | licensecheck, leasecheck, +21 more | src/openreview_cli/app.py:3323 |
| id | argument | client add, client delete | src/openreview_cli/app.py:391 |
| name | argument | client add | src/openreview_cli/app.py:391 |
| config get | command | config | src/openreview_cli/app.py:472 |
| key | argument | config get, config set | src/openreview_cli/app.py:473 |
| config set | command | config | src/openreview_cli/app.py:484 |
| value | argument | config set | src/openreview_cli/app.py:485 |
| pii list | command | pii | src/openreview_cli/app.py:507 |
| --format | option | pii list | src/openreview_cli/app.py:509 |
| pii delete | command | pii | src/openreview_cli/app.py:577 |
| pii cleanup | command | pii | src/openreview_cli/app.py:597 |
| --dry-run | option | pii cleanup | src/openreview_cli/app.py:599 |
| v1 | argument | playbook diff | src/openreview_cli/app.py:944 |
| v2 | argument | playbook diff | src/openreview_cli/app.py:945 |
| --json | option | playbook diff | src/openreview_cli/app.py:946 |
| --document | option | precheck | src/openreview_cli/app.py:1205 |
| --pii-threshold | option | precheck | src/openreview_cli/app.py:1212 |
| --format | option | precheck | src/openreview_cli/app.py:1219 |
| --force-reprocess | option | precheck | src/openreview_cli/app.py:1221 |
| --extraction-model | option | precheck review, precheck compare | src/openreview_cli/app.py:1304 |
| --qa-model | option | precheck review, precheck compare | src/openreview_cli/app.py:1308 |
| --grounding-mode | option | precheck review, precheck compare | src/openreview_cli/app.py:1320 |
| --no-grounding | option | precheck review, precheck compare | src/openreview_cli/app.py:1324 |
| --comparison-model | option | precheck compare | src/openreview_cli/app.py:1854 |
| --format | option | precheck compare | src/openreview_cli/app.py:1877 |
| --align-only | option | precheck compare | src/openreview_cli/app.py:1882 |
| --verbose | option | precheck compare | src/openreview_cli/app.py:1885 |
| --conservative | option | precheck compare | src/openreview_cli/app.py:1895 |
| --json | option | gateway providers, gateway models | src/openreview_cli/app.py:1461 |
| provider | argument | gateway models | src/openreview_cli/app.py:1510 |
| --no-discover | option | gateway models | src/openreview_cli/app.py:1513 |
| slot | argument | gateway set, gateway fallback, +1 more | src/openreview_cli/app.py:1585 |
| model | argument | gateway set | src/openreview_cli/app.py:1585 |
| model | argument | gateway fallback | src/openreview_cli/app.py:1611 |
| --clear | option | gateway fallback | src/openreview_cli/app.py:1613 |
| --today | option | gateway costs | src/openreview_cli/app.py:1709 |
| --session | option | gateway costs | src/openreview_cli/app.py:1710 |
| name | argument | gateway provider add | src/openreview_cli/app.py:1736 |
| --base-url | option | gateway provider add | src/openreview_cli/app.py:1737 |
| --env-key | option | gateway provider add | src/openreview_cli/app.py:1739 |
| --cred | option | gateway provider add | src/openreview_cli/app.py:1742 |
| --cap-embedding | option | gateway provider add | src/openreview_cli/app.py:1744 |
| --cap-reasoning | option | gateway provider add | src/openreview_cli/app.py:1745 |
| --cap-tool-call | option | gateway provider add | src/openreview_cli/app.py:1746 |
| --context-window | option | gateway provider add | src/openreview_cli/app.py:1748 |
| graph build | command | graph | src/openreview_cli/app.py:2644 |
| input_path | argument | graph build | src/openreview_cli/app.py:2647 |
| --store | option | graph build | src/openreview_cli/app.py:2656 |
| --contract-id | option | graph build | src/openreview_cli/app.py:2658 |
| --db-path | option | graph build, graph metrics, +2 more | src/openreview_cli/app.py:2662 |
| --cluster-clauses | option | graph build | src/openreview_cli/app.py:2667 |
| graph metrics | command | graph | src/openreview_cli/app.py:2710 |
| graph_path | argument | graph metrics, graph health, +1 more | src/openreview_cli/app.py:2713 |
| --from-db | option | graph metrics, graph health, +1 more | src/openreview_cli/app.py:2715 |
| --contract-id | option | graph metrics, graph health, +1 more | src/openreview_cli/app.py:2717 |
| file_b | argument | graph diff | src/openreview_cli/app.py:2773 |
| --json | option | graph diff | src/openreview_cli/app.py:2774 |
| graph health | command | graph | src/openreview_cli/app.py:2853 |
| --weights | option | graph health | src/openreview_cli/app.py:2860 |
| graph view | command | graph | src/openreview_cli/app.py:2937 |
| benchmark run | command | benchmark | src/openreview_cli/benchmark/cli.py:56 |
| --datasets | option | benchmark run | src/openreview_cli/benchmark/cli.py:60 |
| --slots | option | benchmark run | src/openreview_cli/benchmark/cli.py:65 |
| --modes | option | benchmark run, benchmark baseline | src/openreview_cli/benchmark/cli.py:70 |
| --prompt-variant | option | benchmark run | src/openreview_cli/benchmark/cli.py:75 |
| --ci | option | benchmark run | src/openreview_cli/benchmark/cli.py:85 |
| --compare | option | benchmark run | src/openreview_cli/benchmark/cli.py:90 |
| --save-baseline | option | benchmark run | src/openreview_cli/benchmark/cli.py:95 |
| --download-datasets | option | benchmark run | src/openreview_cli/benchmark/cli.py:100 |
| --memory-watch | option | benchmark run | src/openreview_cli/benchmark/cli.py:105 |
| --multi-party | option | benchmark run | src/openreview_cli/benchmark/cli.py:110 |
| --format | option | benchmark run, benchmark baseline | src/openreview_cli/benchmark/cli.py:115 |
| --verbose | option | benchmark run | src/openreview_cli/benchmark/cli.py:125 |
| --hallucination-method | option | benchmark run | src/openreview_cli/benchmark/cli.py:130 |
| --use-pipeline | option | benchmark run | src/openreview_cli/benchmark/cli.py:135 |
| --benchmark-tier | option | benchmark run | src/openreview_cli/benchmark/cli.py:140 |
| --datasets | option | benchmark baseline | src/openreview_cli/benchmark/cli.py:361 |
| --provider | option | benchmark baseline | src/openreview_cli/benchmark/cli.py:366 |
| --save-baseline | option | benchmark baseline | src/openreview_cli/benchmark/cli.py:381 |
| prompt create | command | prompt | src/openreview_cli/prompts/cli.py:34 |
| --name | option | prompt create | src/openreview_cli/prompts/cli.py:36 |
| --content | option | prompt create | src/openreview_cli/prompts/cli.py:37 |
| --tags | option | prompt create, prompt update | src/openreview_cli/prompts/cli.py:38 |
| --description | option | prompt create | src/openreview_cli/prompts/cli.py:40 |
| prompt update | command | prompt | src/openreview_cli/prompts/cli.py:56 |
| name | argument | prompt update, prompt show, +3 more | src/openreview_cli/prompts/cli.py:58 |
| --content | option | prompt update | src/openreview_cli/prompts/cli.py:59 |
| --description | option | prompt update | src/openreview_cli/prompts/cli.py:61 |
| prompt list | command | prompt | src/openreview_cli/prompts/cli.py:72 |
| prompt delete | command | prompt | src/openreview_cli/prompts/cli.py:112 |
| --from | option | prompt diff | src/openreview_cli/prompts/cli.py:130 |
| --to | option | prompt diff | src/openreview_cli/prompts/cli.py:131 |
| prompt bind | command | prompt | src/openreview_cli/prompts/cli.py:150 |
| --slot | option | prompt bind, prompt unbind | src/openreview_cli/prompts/cli.py:152 |
| --prompt | option | prompt bind, prompt test, +1 more | src/openreview_cli/prompts/cli.py:153 |
| prompt unbind | command | prompt | src/openreview_cli/prompts/cli.py:164 |
| prompt bindings | command | prompt | src/openreview_cli/prompts/cli.py:176 |
| prompt test | command | prompt | src/openreview_cli/prompts/cli.py:212 |
| --benchmark | option | prompt test, prompt optimize | src/openreview_cli/prompts/cli.py:218 |
| prompt export | command | prompt | src/openreview_cli/prompts/cli.py:239 |
| name | argument | prompt export | src/openreview_cli/prompts/cli.py:241 |
| prompt optimize | command | prompt | src/openreview_cli/prompts/cli.py:287 |
| --iterations | option | prompt optimize | src/openreview_cli/prompts/cli.py:291 |

## Unmatched TUI items

| Item | Type | Owner | Source |
|---|---|---|---|
| ctrl+c | binding | OpenReviewApp | src/openreview_cli/tui/app.py:25 |
| 1 | binding | OpenReviewApp | src/openreview_cli/tui/app.py:26 |
| 5 | binding | OpenReviewApp | src/openreview_cli/tui/app.py:30 |
| / | binding | OpenReviewApp | src/openreview_cli/tui/app.py:31 |
| action_quit_or_warn | action | OpenReviewApp | src/openreview_cli/tui/app.py:72 |
| action_open_search | action | OpenReviewApp | src/openreview_cli/tui/app.py:118 |
| AnnotateModal | screen | openreview_cli.tui.screens.amber_queue | src/openreview_cli/tui/screens/amber_queue.py:54 |
| escape | binding | AnnotateModal, EgressReviewModal, +2 more | src/openreview_cli/tui/screens/amber_queue.py:68 |
| action_cancel | action | AnnotateModal, EgressReviewModal | src/openreview_cli/tui/screens/amber_queue.py:87 |
| AmberQueueScreen | screen | openreview_cli.tui.screens.amber_queue | src/openreview_cli/tui/screens/amber_queue.py:100 |
| r | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:117 |
| s | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:119 |
| j | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:120 |
| down | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:121 |
| up | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:123 |
| t | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:124 |
| o | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:125 |
| escape | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:126 |
| q | binding | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:127 |
| action_accept | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:228 |
| action_reject | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:231 |
| action_next | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:234 |
| action_previous | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:237 |
| action_toggle_overview | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:240 |
| action_annotate | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:244 |
| action_close | action | AmberQueueScreen | src/openreview_cli/tui/screens/amber_queue.py:250 |
| escape | binding | ClientDetailScreen | src/openreview_cli/tui/screens/client_detail.py:27 |
| action_pop_screen | action | ClientDetailScreen | src/openreview_cli/tui/screens/client_detail.py:98 |
| ConfirmModal | screen | openreview_cli.tui.screens.confirm | src/openreview_cli/tui/screens/confirm.py:13 |
| DatabaseErrorScreen | screen | openreview_cli.tui.screens.db_error | src/openreview_cli/tui/screens/db_error.py:15 |
| action_confirm | action | EgressReviewModal | src/openreview_cli/tui/screens/egress_review.py:53 |
| NegotiationProgressScreen | screen | openreview_cli.tui.screens.negotiation_progress | src/openreview_cli/tui/screens/negotiation_progress.py:16 |
| NegotiationResultScreen | screen | openreview_cli.tui.screens.negotiation_result | src/openreview_cli/tui/screens/negotiation_result.py:19 |
| escape | binding | NegotiationResultScreen, ResultScreen, +1 more | src/openreview_cli/tui/screens/negotiation_result.py:32 |
| action_close | action | NegotiationResultScreen, ResultScreen, +1 more | src/openreview_cli/tui/screens/negotiation_result.py:71 |
| NegotiationWizard | screen | openreview_cli.tui.screens.negotiation_wizard | src/openreview_cli/tui/screens/negotiation_wizard.py:66 |
| ctrl+h | binding | NegotiationWizard, ReviewWizard | src/openreview_cli/tui/screens/negotiation_wizard.py:82 |
| action_toggle_hidden | action | NegotiationWizard | src/openreview_cli/tui/screens/negotiation_wizard.py:137 |
| action_cancel_wizard | action | NegotiationWizard, ReviewWizard | src/openreview_cli/tui/screens/negotiation_wizard.py:180 |
| ProgressScreen | screen | openreview_cli.tui.screens.progress | src/openreview_cli/tui/screens/progress.py:45 |
| ResultScreen | screen | openreview_cli.tui.screens.result | src/openreview_cli/tui/screens/result.py:34 |
| l | binding | ResultScreen | src/openreview_cli/tui/screens/result.py:52 |
| t | binding | ResultScreen | src/openreview_cli/tui/screens/result.py:53 |
| right | binding | ResultScreen | src/openreview_cli/tui/screens/result.py:57 |
| left | binding | ResultScreen | src/openreview_cli/tui/screens/result.py:58 |
| action_toggle_layout | action | ResultScreen | src/openreview_cli/tui/screens/result.py:264 |
| action_open_amber_queue | action | ResultScreen | src/openreview_cli/tui/screens/result.py:277 |
| action_toggle_hidden | action | ReviewWizard | src/openreview_cli/tui/screens/review_wizard.py:280 |
| SearchScreen | screen | openreview_cli.tui.screens.search | src/openreview_cli/tui/screens/search.py:31 |

## Semantic collisions

### `--all`

- Also list clean documents (no PII) (owners: pii list; sources: src/openreview_cli/app.py:510).
- Clear ALL indexes (requires confirmation). (owners: index-clear; sources: src/openreview_cli/app.py:2516).
- Delete ALL playbooks (owners: playbook delete; sources: src/openreview_cli/app.py:1053).
- Export all playbooks (owners: playbook export; sources: src/openreview_cli/app.py:842).
- Run all datasets, slots, and modes (owners: benchmark run; sources: src/openreview_cli/benchmark/cli.py:80).

### `--confidence-threshold`

- Amber boundary for divergence detection confidence (0.0-1.0). Independent of single-party threshold. Note: accuracy ceiling ~64% F1 - set generously. (owners: precheck compare; sources: src/openreview_cli/app.py:1858).
- Confidence threshold for Amber flagging (0.0-1.0). (owners: negotiate; sources: src/openreview_cli/app.py:3025).
- Confidence threshold for Green/Amber/Red (0.0-1.0). (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +19 more; sources: src/openreview_cli/app.py:3316).
- Confidence threshold for Green/Amber/Red assignment (0.0-1.0). Clauses with effective confidence below this threshold are marked Amber. Note: The comparison accuracy of automated review is bounded by approximately 64% F1. Three-color output (Green/Amber/Red) is designed to mitigate this - set the threshold generously to push uncertain comparisons to Amber rather than risking false Green or Red. (owners: precheck review; sources: src/openreview_cli/app.py:1328).

### `--content`

- New prompt content (owners: prompt update; sources: src/openreview_cli/prompts/cli.py:59).
- Prompt instruction text (max 16 KB) (owners: prompt create; sources: src/openreview_cli/prompts/cli.py:37).

### `--contract-id`

- Contract ID for SQLite storage (default: input file stem). (owners: graph build; sources: src/openreview_cli/app.py:2658).
- Contract ID in SQLite (required with --from-db). (owners: graph metrics, graph health, graph view; sources: src/openreview_cli/app.py:2717, src/openreview_cli/app.py:2868, src/openreview_cli/app.py:2944).

### `--datasets`

- Comma-separated datasets (owners: benchmark baseline; sources: src/openreview_cli/benchmark/cli.py:361).
- Comma-separated list of datasets: cuad,maud,contract_nli,pii (owners: benchmark run; sources: src/openreview_cli/benchmark/cli.py:60).

### `--description`

- Human-readable description (owners: prompt create; sources: src/openreview_cli/prompts/cli.py:40).
- Updated description (owners: prompt update; sources: src/openreview_cli/prompts/cli.py:61).

### `--force`

- Delete client and all associated reviews. (owners: client delete; sources: src/openreview_cli/app.py:428).
- Skip confirmation (owners: prompt delete; sources: src/openreview_cli/prompts/cli.py:115).
- Skip confirmation prompt (owners: playbook delete; sources: src/openreview_cli/app.py:1054).
- Suppress overwrite warning (owners: playbook export; sources: src/openreview_cli/app.py:841).

### `--format`

- Export format: md, json, docx. (owners: export; sources: src/openreview_cli/app.py:3209).
- Output format: json, terminal (owners: benchmark run, benchmark baseline; sources: src/openreview_cli/benchmark/cli.py:115, src/openreview_cli/benchmark/cli.py:371).
- Output format: table, json (owners: pii list; sources: src/openreview_cli/app.py:509).
- Output format: table, json, memo. (owners: negotiate; sources: src/openreview_cli/app.py:3033).
- Output format: terminal, json (owners: retrieve; sources: src/openreview_cli/app.py:2257).
- Output format: text (terminal) or json. (owners: precheck compare; sources: src/openreview_cli/app.py:1877).
- Output format: text or json. (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +20 more; sources: src/openreview_cli/app.py:3299, src/openreview_cli/app.py:1284).
- Output format: text, json (owners: parse, chunk; sources: src/openreview_cli/app.py:1386, src/openreview_cli/app.py:1804).
- Output format: text, json. (owners: precheck; sources: src/openreview_cli/app.py:1219).

### `--json`

-  (owners: gateway providers, gateway models; sources: src/openreview_cli/app.py:1461, src/openreview_cli/app.py:1511).
- Output as JSON. (owners: graph diff; sources: src/openreview_cli/app.py:2774).
- Output diff as JSON (owners: playbook diff; sources: src/openreview_cli/app.py:946).

### `--memo-format`

- Export format(s) for the review memo. Supported values: md (Markdown), json (JSON), docx (Word document). May be specified multiple times to produce multiple formats in one run. (owners: precheck review; sources: src/openreview_cli/app.py:1290).
- Export format(s) for the review memo. Supported: md, json, docx. (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +19 more; sources: src/openreview_cli/app.py:3305).

### `--method`

- Retrieval method: sparse, dense, hybrid (owners: retrieve; sources: src/openreview_cli/app.py:2245).
- Retrieval method: sparse, hybrid (owners: ingest; sources: src/openreview_cli/app.py:2107).

### `--no-pii`

- Disable PII stripping. Processes raw text. (owners: precheck; sources: src/openreview_cli/app.py:1208).
- Skip PII stripping on both documents. (owners: precheck compare; sources: src/openreview_cli/app.py:1887).
- Skip PII stripping. (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +20 more; sources: src/openreview_cli/app.py:3295, src/openreview_cli/app.py:1316).

### `--output`

- Destination file path (or directory with --all) (owners: playbook export; sources: src/openreview_cli/app.py:839).
- Output directory for review results. (owners: precheck; sources: src/openreview_cli/app.py:1217).
- Output file path (default: stdout) (owners: prompt export; sources: src/openreview_cli/prompts/cli.py:242).
- Path for the output graph JSON file (default: {input_stem}.graph.json). (owners: graph build; sources: src/openreview_cli/app.py:2652).
- Write JSON report to file path (owners: benchmark run; sources: src/openreview_cli/benchmark/cli.py:120).
- Write output to file instead of stdout. (owners: negotiate, licensecheck, leasecheck, privacycheck, +22 more; sources: src/openreview_cli/app.py:3031, src/openreview_cli/app.py:3301, src/openreview_cli/app.py:1286, src/openreview_cli/app.py:1879).
- Write output to file path (owners: benchmark baseline; sources: src/openreview_cli/benchmark/cli.py:376).

### `--output-dir`

- Directory for exported files. (owners: export; sources: src/openreview_cli/app.py:3211).
- Directory for memo files. Defaults to review_results/. (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +19 more; sources: src/openreview_cli/app.py:3310).
- Directory where memo files are written. Created automatically if it does not exist. Defaults to review_results/ in the current working directory. (owners: precheck review; sources: src/openreview_cli/app.py:1297).

### `--playbook`

- Path to a custom YAML playbook override. (owners: licensecheck, leasecheck, privacycheck, privacycheck_v2, +19 more; sources: src/openreview_cli/app.py:3297).
- Playbook ID to load from database. (owners: precheck review; sources: src/openreview_cli/app.py:1282).

### `--playbook-path`

- Path to a custom YAML playbook override. (owners: precheck review; sources: src/openreview_cli/app.py:1279).
- Path to a custom YAML playbook. (owners: negotiate; sources: src/openreview_cli/app.py:2999).

### `--save-baseline`

- Save as official baseline (requires --format json and --output) (owners: benchmark baseline; sources: src/openreview_cli/benchmark/cli.py:381).
- Save this run as the regression baseline (owners: benchmark run; sources: src/openreview_cli/benchmark/cli.py:95).

### `--verbose`

- Detailed per-item progress (owners: benchmark run; sources: src/openreview_cli/benchmark/cli.py:125).
- Enable info-level logging (startup diagnostics). (owners: openreview; sources: src/openreview_cli/app.py:360).
- Show full RCBSF classification and rationale. (owners: precheck compare; sources: src/openreview_cli/app.py:1885).
- Show per-clause progress. (owners: negotiate, licensecheck, leasecheck, privacycheck, +21 more; sources: src/openreview_cli/app.py:3029, src/openreview_cli/app.py:3313, src/openreview_cli/app.py:1317).

### `--version`

- Prompt version (owners: prompt bind; sources: src/openreview_cli/prompts/cli.py:154).
- Show the openreview version and exit. (owners: openreview; sources: src/openreview_cli/app.py:348).
- Specific version (default: latest) (owners: prompt show; sources: src/openreview_cli/prompts/cli.py:92).
- Version to export (default: current/latest) (owners: playbook export; sources: src/openreview_cli/app.py:836).

### `--weights`

- Five custom weights: density depth orphans broken-refs coverage. Space-separated, e.g. --weights '0.15 0.20 0.20 0.25 0.20'. Auto-normalised to sum 1.0. (owners: graph health; sources: src/openreview_cli/app.py:2860).
- Payoff component weights as comma-separated values: risk,financial,obligation (e.g. 0.7,0.15,0.15). Must sum to ~1.0. (owners: negotiate; sources: src/openreview_cli/app.py:3018).

## Row counts

| Row type | Count |
|---|---|
| action | 27 |
| app | 1 |
| argument | 73 |
| binding | 37 |
| command | 82 |
| default-state | 10 |
| group | 11 |
| mismatch | 1 |
| option | 390 |
| screen | 19 |
| shared-call-arg | 84 |
| total | 735 |

Regenerate with:

```bash
uv run python scripts/parity/inventory_cli.py --out draft/parity/cli-inventory.json
uv run python scripts/parity/inventory_tui.py --out draft/parity/tui-inventory.json
uv run python scripts/parity/build_parity_matrix.py --cli-json draft/parity/cli-inventory.json --tui-json draft/parity/tui-inventory.json
```
