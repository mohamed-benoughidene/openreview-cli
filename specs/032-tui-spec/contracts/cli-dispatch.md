# CLI Dispatch Contract

| Invocation | TTY? | Behavior | Exit code |
|---|---|---|---|
| `openreview` | yes | Launch TUI (`launch_tui()`) | 0 (after user quits) |
| `openreview` | no | Print friendly message, exit | 0 |
| `openreview --no-tui` | either | Print help and exit (no TUI launched, no subcommand required) | 0 |
| `openreview --no-tui parse foo.pdf` | either | Run `parse` subcommand (unchanged) | existing |
| `openreview <subcommand>` | either | Run subcommand (unchanged) | existing |
| `openreview --version` | either | Print version and exit | 0 |
| `openreview --help` | either | Print help and exit | 0 |

## TTY detection

- Function: `sys.stdin.isatty()`
- Checked at: `src/openreview_cli/tui/launcher.py`, BEFORE any Textual import
- Rationale: avoids the cost of importing Textual when the TUI cannot run
- Note: stdout redirection (e.g. `openreview > out.log`) does NOT affect TTY detection, since the check is on stdin only. The TUI works in this case.
