# Contract — CLI / TUI Surface (Spec 034)

Phase 1 output. The command + output contract touched by 034.

## `openreview gateway providers --json` (app.py:1346)

Output shape change (FR-4) — per-field status:

```json
{
  "providers": [
    {
      "name": "bedrock",
      "base_url": null,
      "is_local": false,
      "source": "bundled",
      "capabilities": { "...": "..." },
      "credentials": [
        {"env_key": "AWS_ACCESS_KEY_ID", "label": "AWS Access Key", "required": true, "resolved": true,  "secret": true},
        {"env_key": "AWS_SECRET_ACCESS_KEY", "label": "AWS Secret Key", "required": true, "resolved": false, "secret": true},
        {"env_key": "AWS_REGION_NAME", "label": "AWS Region", "required": true, "resolved": true, "secret": false}
      ],
      "configured": false
    }
  ]
}
```

Rules:
- `resolved` = env or auth-store has a non-empty value for `env_key`.
- `secret=true` fields: `resolved` may be `true/false` but the VALUE is never emitted (redacted).
- `configured` = every `required=true` credential `resolved`. Single-key providers keep
  `api_key_env` + `configured` from `env_key` (backward compatible).

## `openreview gateway provider add` (FR-5)

Repeatable `--cred` (typer list-option, Context7 confirmed):

```bash
openreview gateway provider add bedrock \
  --cred AWS_ACCESS_KEY_ID=AKIA... \
  --cred AWS_SECRET_ACCESS_KEY=... \
  --cred AWS_REGION_NAME=us-east-1
```

- Each `--cred key=value` parsed; `key` must match a `CredentialField.env_key` of the
  provider; `value` stored in `auth.json` under `{provider: {key: value}}` (mode 600).
- `is_file_path=true` values validated (exists + readable) before storing.

## Wizard (gateway/wizard.py — questionary)

- Iterates `provider.credentials`; prompts per field using `label`.
- `secret=true` → masked input. `is_file_path=true` → path prompt + existence/readability
  check (FR-7). `required=false` → skippable.
- On finish, writes the same `auth.json` mapping as `provider add`.

## TUI health check

Currently `os.environ.get(info.env_key)`. FR-4: replace with per-field resolution over
`info.credentials` (or fall back to `env_key` when list empty). Provider shown
"configured" only when all required fields resolve.
