# Phase 2–8 — Config + Storage Foundation

**Date:** 2026-06-24
**Commit:** `018c4ba` (reports folder) | `8d6b1f0` (current HEAD)
**Audience:** non-technical stakeholder learning Python through this project
**Teaching method:** Pain → Recipe → Practice

## Part 1 — Status

### What this phase was

We added the guts the product needs to survive a CLI session: persistent configuration (config.yml for settings, auth.json for secrets), a local database (SQLite) for reviews and cost tracking, CLI commands to view/modify settings and manage API clients, and overrides via environment variables. Then we polished everything (speed, memory, spec alignment) and did a full bloat audit (cut 120 lines, 5 files).

### What changed

**New capabilities:**
- `openreview config show` — prints the full configuration as a table
- `openreview config get <key>` — looks up a single setting by dotted path (e.g. `openreview config get provider`)
- `openreview config set <key> <value>` — sets a setting, with type detection and a safety backup
- `openreview client add <name>` — registers an API client (API key prompted interactively)
- `openreview client list` — lists registered clients
- `openreview client delete <name>` — removes a client; refuses if client has reviews unless `--force` passed
- Environment variable overrides: `OPENREVIEW_PROVIDER=ollama openreview config show` or `OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS=300` for nested keys
- Provider API keys can also live in environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_HOST`)
- Cost tracking logs each review: cost per review, total daily cost, and a hard ceiling check before every review

**Files created:**
- `src/openreview_cli/config/` — package for config handling (paths, loader, auth)
- `src/openreview_cli/config/paths.py` — resolves XDG paths for config/data/log dirs
- `src/openreview_cli/config/loader.py` — config model (Pydantic), YAML reading/writing, env var override, dotted-path get/set
- `src/openreview_cli/config/auth.py` — auth.json creation, reading, loading with env var merge, permission fix
- `src/openreview_cli/storage/` — package for database handling
- `src/openreview_cli/storage/database.py` — SQLite connection, transaction manager, migration runner, cost/limit/table functions
- `src/openreview_cli/storage/migrations/001_initial.sql` — schema: 5 tables (clients, reviews, review_diffs, cost_logs, config_version)
- `src/openreview_cli/errors.py` — exit-code helpers (config missing = code 5, cost over limit = code 6)
- `tests/unit/test_config_loader.py` — 6 tests
- `tests/unit/test_auth.py` — 5 tests
- `tests/unit/test_database.py` — 7 tests
- `tests/unit/test_cli_config.py` — 8 tests
- `tests/unit/test_cli_client.py` — 5 tests

**Files deleted (ponytail bloat audit):**
- `src/openreview_cli/_version.py` — merged 1 line into `__init__.py`
- `src/openreview_cli/config/defaults.py` — inlined into `loader.py` as a constant
- `src/openreview_cli/logging_config.py` — inlined into `app.py`
- `tests/fixtures/valid_config.yml` — was never used by any test
- `tests/fixtures/invalid_config.yml` — was never used by any test
- `tests/fixtures/.gitkeep` — emptied the fixtures directory

### What was verified

- **36 unit tests pass** in 1.79 seconds (was 4 tests in Phase 1)
- **ruff** (linter) — clean
- **ruff format** — 20 files formatted
- **mypy** (strict) — clean
- **Memory budget** — `pytest -m memory` passes (peak under 110 MB)
- **Warm startup** — `openreview --version` on a configured system completes in under 0.3 seconds
- **Spec validation** — end-to-end: create config, set values, read them back, everything matches the spec

---

## Part 2 — Concepts

### 10. SQLite database (the filing cabinet)

**The Pain.** Without a database, each CLI run starts fresh. Last week's review data, client API keys, and cost totals vanish when you close the terminal. You could store everything in JSON files, but then you'd be writing your own logic to search through them, merge them, and keep them from corrupting when two things write at once.

**The Recipe.** SQLite is a filing cabinet where each drawer is a "table" (a spreadsheet), each folder is a "row" (one record), and each field on the folder is a "column" (a piece of data). Python ships with SQLite built in — no extra installation needed. In `database.py`:
```python
import sqlite3

def get_connection(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn
```
- `sqlite3.connect(str(db_path))` = "open the drawer (the file) at this path"
- `PRAGMA journal_mode=WAL` = "use Write-Ahead Logging — lets you read from the cabinet while someone else is writing"
- `PRAGMA foreign_keys=ON` = "don't let me delete a client that still has reviews in the reviews drawer"
- `row_factory = sqlite3.Row` = "return each record as a named item (like a dictionary), not a position-numbered list"

**In Practice.** When you type `openreview client list`, the CLI opens the SQLite file (`openreview.db`), executes `SELECT * FROM clients`, gets back a list of rows (each with a `name` and `display_name`), and prints them. When you log a review cost, it runs `INSERT INTO cost_logs (...) VALUES (...)` — one row per review, always growing. The filing cabinet is the `openreview.db` file at `~/.local/share/openreview/openreview.db` (Linux) or the equivalent Windows path.

---

### 11. Migration (installing new shelves in an existing cabinet)

**The Pain.** You ship version 1 of the app with a `clients` table. In version 2, you need to add a `cost_logs` table and a `config_version` table. If you just drop and recreate the database file on every upgrade, existing users lose their data. If you write an `if not exists` check for every table, you'll have messy code that's hard to follow.

**The Recipe.** A migration is a numbered instruction sheet that installs new shelves into an existing cabinet. The first migration (`001_initial.sql`) creates all 5 tables. When the app starts, it runs migrations in order and tracks which ones have been applied. It only runs migrations that haven't run yet. In `database.py`:
```python
def run_migrations(conn):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS config_version ("
        "  migration_id INTEGER PRIMARY KEY, applied_at TEXT NOT NULL"
        ")"
    )
    cur = conn.execute("SELECT COALESCE(MAX(migration_id), 0) FROM config_version")
    current = cur.fetchone()[0]
    migration_dir = Path(__file__).parent / "migrations"
    for path in sorted(migration_dir.glob("*.sql")):
        migration_id = int(path.stem.split("_")[0])
        if migration_id > current:
            sql = path.read_text()
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO config_version (migration_id, applied_at) VALUES (?, ?)",
                (migration_id, datetime.utcnow().isoformat()),
            )
```
- It creates a `config_version` table first (to track which migrations ran)
- It checks the highest migration number already applied
- It runs every `.sql` file with a higher number, in filename order
- Each migration records itself as done so it never runs again

**In Practice.** When you run `openreview` after upgrading from v1 to v2, the migration runner sees `MIGRATION 1` is already applied (the `config_version` table says so), so it applies migration 2 (`002_add_cost_logs.sql`). The user never notices — their data survived, the new table appeared, and the app keeps working.

---

### 12. Context manager with `with` (the "open, use, close" handshake)

**The Pain.** Every database operation follows a pattern: open the connection, do the work, save the changes, close the connection. If you forget to close, the file stays locked. If the work fails halfway, you might have half-written data. Without a disciplined pattern, every function repeats the same boilerplate — and one missing `.close()` or missing rollback on error causes a bug.

**The Recipe.** A context manager is a lock that says "open, use it for this block, then clean up when the block ends — even if it crashes." You write `with X` at the start, and Python guarantees the cleanup. In `database.py`:
```python
from contextlib import contextmanager

@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
```
Usage:
```python
with transaction(conn) as tx:
    tx.execute("INSERT INTO clients (name, display_name) VALUES (?, ?)", (name, name))
```
- `with transaction(conn) as tx:` = "open a safe workspace on this connection"
- Inside the block: `tx.execute(...)` = "do work in the workspace"
- After the block, if no errors: `conn.commit()` = "save everything"
- If any error happens: `conn.rollback()` = "undo everything, like it never happened"

**In Practice.** Every function in `database.py` (add_client, delete_client, log_cost, etc.) wraps its database work in `with transaction(conn):`. If the insert fails, the database rolls back to its state before the function started. No partial writes, no orphan data, no forgotten closes.

---

### 13. Pydantic model (the form with built-in validation)

**The Pain.** A config file is just a YAML dictionary: `provider: openai`, `model: gpt-4o`. Without validation, you could write `provider: 42` or `tier: gold_platinum` and YAML would happily load it — your app would crash at runtime when it tried to use these values. You'd need manual `if` checks everywhere.

**The Recipe.** A Pydantic model is a form with strict rules. Each field has a type, a default, and optional validators that check the value. When you load the config into the model, Pydantic validates everything up front. In `loader.py`:
```python
from pydantic import BaseModel, Field, field_validator

class ConfigModel(BaseModel):
    provider: str = "ollama"
    model: str = "qwen2.5:3b"
    tier: str = "local"

    @field_validator("tier")
    @classmethod
    def tier_must_be_valid(cls, v: str) -> str:
        allowed = {"local", "fast", "balanced", "quality", "custom"}
        if v not in allowed:
            raise ValueError(f"tier must be one of {allowed}")
        return v
```
- `class ConfigModel(BaseModel):` = "define a form template"
- `provider: str = "ollama"` = "there's a field called provider, it must be text (not a number), defaults to 'ollama'"
- `@field_validator("tier")` = "before setting tier, run this check"
- Inside the validator: if the value isn't one of the 5 allowed tiers, reject it with an error message

**In Practice.** When the app starts, `load_config()` reads `config.yml`, passes the raw dictionary to `ConfigModel(**data)` — unpacking the dict into named slots. If `config.yml` says `tier: premium_plus`, Pydantic raises a clean error: "tier must be one of 'local', 'fast', 'balanced', 'quality', 'custom'". The user sees the error, fixes the value, and the config loads successfully next time.

---

### 14. Environment variables (the cheat-sheet that overrides settings)

**The Pain.** You're testing the app and need to switch providers: `openreview config set provider ollama`. Then you test again with OpenAI: `openreview config set provider openai`. You keep changing config.yml back and forth. Or you need to run a one-off review with a high cost limit, but you don't want to change config.yml permanently.

**The Recipe.** Environment variables are cheat-sheets that override config.yml temporarily. You set them before running the command, and the change only lasts for that one command. The pattern is: `CONFIG_VALUE` comes first, then `ENV_VAR` overrides it, then the live setting. If no env var is set, the config.yml value wins. In `loader.py`:
```python
def _get_env_overrides():
    overrides = {}
    for key in ("provider", "model", "tier"):
        env_key = f"OPENREVIEW_{key.upper()}"
        if env_key in os.environ:
            overrides[key] = _parse_value(os.environ[env_key])
    return overrides
```
- `f"OPENREVIEW_{key.upper()}"` = "convert `provider` to `OPENREVIEW_PROVIDER`"
- For nested keys like `gateway.cost_limits.per_review_cents`: the env var uses double underscores: `OPENREVIEW_GATEWAY__COST_LIMITS__PER_REVIEW_CENTS`

**In Practice.** Run `OPENREVIEW_PROVIDER=ollama openreview config show` — the output shows provider: ollama, overriding whatever config.yml says. The change affects only that one command. Run `openreview config show` without the env var, and config.yml's value shows again. The env var is a temporary cheat-sheet.

---

### 15. Priority layers (config.yml < env var < CLI flag)

**The Pain.** You have settings coming from your YAML file, environment variables, and command-line flags. They can all set the same thing (like `provider`). Without ordering, it's chaos: which one wins? Last one read? First one found?

**The Recipe.** Priority layers are a ruler that says: config.yml is the baseline (layer 1), env vars override it (layer 2), and CLI flags override both (layer 3 — coming in a later phase). Each layer starts fresh from the layer below. The code merges them in order:
```python
def load_config():
    data = _read_yaml()            # Layer 1: config.yml
    if os.environ:                 # Layer 2: env vars
        data.update(_get_env_overrides())
    return ConfigModel(**data)     # Layer 3: (future) CLI flags
```
- `_read_yaml()` produces `{"provider": "ollama", "model": "qwen2.5:3b", ...}`
- `_get_env_overrides()` produces `{"provider": "openai"}` (if that env var is set)
- `data.update(overrides)` overwrites the baseline provider with the env var value
- The merged dict is validated by Pydantic and returned

**In Practice.** `openreview config show` at layer 1 shows `provider: ollama`. With `OPENREVIEW_PROVIDER=openai`, layer 2 overrides it to `openai`. In a future phase, `openreview --provider openai run review` would override both (layer 3). The ruler is always: lowest number = lowest priority.

---

### 16. Rich table (turning data into a printed grid)

**The Pain.** `openreview config show` returns a Python dictionary of 15+ settings. Without pretty printing, the output is a wall of `{'provider': 'ollama', 'model': 'qwen2.5:3b', ...}` — hard to scan, hard to find the one setting you care about.

**The Recipe.** A Rich table prints data as a formatted grid: columns with headers, rows with values, neatly aligned. In `app.py`:
```python
from rich.console import Console
from rich.table import Table

def _print_config(settings):
    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    for key in sorted(settings):
        table.add_row(key, str(settings[key]))
    Console().print(table)
```
- `Table(title="Configuration")` = "create a table with a header"
- `add_column("Key")` and `add_column("Value")` = "define two columns"
- `sorted(settings)` loops through keys alphabetically
- `add_row(key, str(settings[key]))` = "add one row per setting"
- `Console().print(table)` = "render the table to the terminal"

**In Practice.** `openreview config show` prints:
```
╭───────────────┬──────────────────────╮
│ Configuration │                      │
├───────────────┼──────────────────────┤
│ Key           │ Value                │
├───────────────┼──────────────────────┤
│ model         │ qwen2.5:3b           │
│ provider      │ ollama               │
│ tier          │ local                │
│ ...           │ ...                  │
╰───────────────┴──────────────────────╯
```
Color-coded (cyan keys, green values), alphabetized, readable at a glance.

---

## Part 3 — Walkthrough

Note: The Phase 1 report walked through files that still exist. This walkthrough covers only files added or significantly changed since Phase 1. If a file is not listed here, it hasn't changed meaningfully.

### `src/openreview_cli/__init__.py` — the front door, now with version inline

Phase 1 had `__version__` in a separate `_version.py`. The ponytail audit moved the single line in here to remove an entire file. Now:
```python
__version__ = "0.1.0"
__all__ = ["__version__"]
```
Everything else imports `__version__` from here.

### `src/openreview_cli/app.py` — the vending machine, now with more buttons

Phase 1 had one button (`--version`). Now it has three more buttons: `config` (submachine with show/get/set), `client` (submachine with add/list/delete), and a hidden `--debug` flag.

At the top, internal modules are imported normally (not lazy). Only the heavy dependencies (pydantic, rich) are still lazy-imported inside function bodies.

Inside `_init()`, the logging is now set up directly instead of calling a separate function from `logging_config.py`:
- Creates the log directory (if it doesn't exist)
- Sets up a file handler and a console handler
- Logs rotation: up to 3 MB per file, keeps 3 backups

The `config` group has three commands:
- `config show` — calls `_print_config()` which builds a Rich table
- `config get <key>` — calls `get_config_value(key)` with dot notation
- `config set <key> <value>` — calls `set_config_value(key, value)`, shows a "backup written" message

The `client` group has three commands:
- `client add <name>` — prompts for API key via hidden input, calls `add_client()`
- `client list` — calls `list_clients()`, prints a simple text table
- `client delete <name>` — checks if client has reviews first; if yes, refuses unless `--force` is passed, then cascade-deletes

### `src/openreview_cli/config/paths.py` — the address book

This is a new file. It resolves file paths consistently across operating systems:

```python
from platformdirs import PlatformDirs

_DIRS = PlatformDirs("openreview", "openreview")

def get_config_dir() -> Path:
    return Path(_DIRS.user_config_dir)

def get_data_dir() -> Path:
    return Path(_DIRS.user_data_dir)

def get_log_dir() -> Path:
    return Path(_DIRS.user_log_dir)
```

- On Linux: config = `~/.config/openreview/`, data = `~/.local/share/openreview/`, log = `~/.local/share/openreview/logs/`
- On Windows: config = `C:/Users/You/AppData/Local/openreview/`, data = same pattern, logs similarly

Every other module imports these three functions instead of hardcoding paths.

### `src/openreview_cli/config/loader.py` — the settings desk

This is the biggest new file. It does four jobs:

1. **Define the config form** (`ConfigModel`) — a Pydantic model with fields for provider, model, tier, and gateway settings. Each field has defaults and some have validators (tier must be one of 5 values, int fields must be positive).

2. **Load config** (`load_config()`) — reads `config.yml`, creates it with defaults if it doesn't exist, merges env var overrides on top, validates everything through Pydantic, and returns the validated object.

3. **Get/set values by dotted path** (`get_config_value()`, `set_config_value()`) — "provider" returns the top-level provider; "gateway.cost_limits.per_review_cents" walks into nested dicts using the dots as separators. The setter writes a backup of config.yml before modifying it.

4. **Parse string values** (`_parse_value()`) — converts CLI string arguments to proper Python types: `"true"` → `True`, `"123"` → `123`, `"12.5"` → `12.5`.

### `src/openreview_cli/config/auth.py` — the safe

This file manages `auth.json` — the secret storage for API credentials. Secrets live in a separate file from settings for two reasons:
- Security: `auth.json` gets chmod 600 (owner-only read/write) on Unix
- Structure: you might want to version-control config.yml (no secrets) but never auth.json

Functions:
- `ensure_auth()` — creates `auth.json` if it doesn't exist (empty `{}`)
- `load_auth()` — reads auth.json, then merges in any provider API key env vars (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OLLAMA_HOST`) on top of the file contents
- `_fix_permissions()` — sets chmod 600 on Unix, warns on Windows

### `src/openreview_cli/storage/database.py` — the filing cabinet manager

This file manages the SQLite database. Key pieces:

- `get_connection(db_path)` — opens a connection with WAL mode, foreign keys, and Row factory
- `transaction(conn)` — the safe workspace context manager (Concept 12)
- `init_database(db_path)` — creates the database directory, opens a connection, runs migrations
- `run_migrations(conn)` — runs `.sql` files from `migrations/` in order, tracking what's been applied
- `log_cost(conn, client_id, ...)` — inserts a row into `cost_logs` with the review's cost
- `check_daily_limit(conn)` — sums today's costs and compares against the configured daily limit
- `check_review_limit(conn)` — same for per-review limit
- `add_client(conn, name)` — inserts a client record
- `delete_client(conn, name)` — removes a client; checks for reviews first
- `client_has_reviews(conn, name)` — returns True if any reviews reference this client
- `list_clients(conn)` — returns all clients

### `src/openreview_cli/storage/migrations/001_initial.sql` — the cabinet blueprint

Creates 5 tables:
- `config_version` — tracks which migrations have run
- `clients` — stores API client names and display names
- `reviews` — stores review records with foreign key to clients
- `review_diffs` — stores diff chunks per review (file-level granularity)
- `cost_logs` — tracks per-review cost, with foreign key to reviews

### `src/openreview_cli/errors.py` — the error bell

Two simple functions that print an error message and exit with a specific code:
- `config_error(msg)` — exit code 5: configuration problem
- `cost_limit_error(msg)` — exit code 6: cost limit hit

### New test files

Each test file tests one module. The pattern is always the same:
- Mock or isolate the thing being tested (use `tmp_path` for temp files, `monkeypatch` for env vars)
- Set up a known state (create a config file, open a database)
- Run the function
- Assert the result

`tests/unit/test_config_loader.py` — 6 tests:
- Creating config from scratch with defaults
- Loading an existing config file
- Reading a single setting by dotted path
- Writing a setting and verifying the file changed
- Validating tier values (rejecting invalid ones)
- Env var override priority

`tests/unit/test_auth.py` — 5 tests:
- Creating auth.json when missing
- Reading auth.json
- Permission fix on startup
- Loading with provider API key env vars
- Load handles missing file gracefully

`tests/unit/test_database.py` — 7 tests:
- Database initialization creates the file
- Running migrations is idempotent (safe to run twice)
- Inserting a cost log
- Daily cost limit check
- Per-review cost limit check
- Add/list/delete clients
- Delete refuses if reviews exist (tests `--force` safety)

`tests/unit/test_cli_config.py` — 8 tests:
- `config show` renders output
- `config get` returns a value
- `config get` with unknown key shows error
- `config set` modifies the file
- `config set` with type conversion works
- `config show` creates config if missing (lazy init)
- Warm startup latency (<0.3s)
- Backup file created before set

`tests/unit/test_cli_client.py` — 5 tests:
- `client add` registers a client
- `client list` returns them
- `client delete` removes one
- `client delete` with `--force` cascade-deletes reviews
- Adding duplicate client fails gracefully

### `specs/001-config-storage-foundation/tasks.md` — the blueprint of what was built

56 tasks, all checked off. Each task is a single atomic unit (typically 1-2 hours of work): `T001` through `T056`. The file lists every module, every test, every migration. All 56 are now marked `[X]`.

---

## What's next

The foundation is fully laid. The next phase picks up the first product mode — most likely the CLI resolver (connect to a provider, handle prompts, stream responses) or the review pipeline (feed a contract through an LLM, get structured findings). This is where the heavy dependencies land: `litellm` for provider abstraction, `PyMuPDF` for PDF parsing, `presidio-analyzer` for PII detection, `docling` for document ingestion.

## Questions for the stakeholder

- The spec calls for 22 product modes (precheck, hirecheck, dealcheck, ...). Which one should we build first? The most practical candidate is `precheck` (quick NDA/review of a single document) — it exercises the full pipeline from file input → LLM analysis → structured output with the fewest moving parts.
