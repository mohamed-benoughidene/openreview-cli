# TUI Internal Events

The TUI uses Textual's message bus internally. No new public events are introduced to the rest of the codebase.

## Domain layer calls (TUI → existing code)

| Event | Source | Target | Notes |
|---|---|---|---|
| `gateway_health_check` | `tui/domain/gateway.py` | `openreview_cli.gateway.router.Gateway.health_check` | existing API |
| `gateway_set_slot` | `tui/screens/gateway_wizard.py` | `openreview_cli.config.loader.set_config_value` | existing API |
| `review_run` | `tui/screens/review_wizard.py` | `openreview_cli.review.run_review` | existing API; PII stripping enabled by default |
| `client_list` | `tui/tabs/clients.py` | `openreview_cli.storage.database` client CRUD | existing API |
| `playbook_list` | `tui/tabs/playbooks.py` | `openreview_cli.review.playbook.load_playbook` + storage | existing API |
| `privacy_tier_read` | `tui/domain/privacy.py` | `openreview_cli.gateway.tier_config.TierConfig.from_config` | existing API |

## Domain layer write paths (TUI → existing storage)

| Action | Source | Target | Notes |
|---|---|---|---|
| `client_create` | `tui/screens/client_form.py` | `add_client` in storage | PII not applicable (no document text) |
| `client_delete` | `tui/tabs/clients.py` | `delete_client` in storage | may cascade-delete reviews per user choice |
| `playbook_import` | `tui/tabs/playbooks.py` | `import_playbook_yaml` in storage | YAML file passed as-is |
| `gateway_save_key` | `tui/screens/gateway_wizard.py` | `openreview_cli.config.auth` | key written to `auth.json` chmod 600 |

## Privacy invariants

- TUI does NOT bypass PII stripping. `run_review` is always called with `pii_enabled=True` (default) unless the user explicitly ticks "Disable PII stripping" in the wizard's step 4.
- TUI does NOT write raw contract text to logs. Even in debug mode, logs are filtered.
- TUI does NOT introduce new network endpoints. All network calls go through the existing `gateway.router.Gateway`.
