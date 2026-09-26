# Research: Config + Storage Foundation

**Phase**: 0 (Research & Consolidation)
**Date**: 2026-06-24
**Sources**: context7 (current docs for each technology)

## 1. PyYAML — YAML Configuration Parsing

### Decision
Use `yaml.safe_load()` for reading and `yaml.safe_dump()` for writing. Always with `default_flow_style=False` for human-readable output.

### Rationale
`safe_load` prevents arbitrary code execution from untrusted YAML input. The YAML config file is user-editable, so it could contain malicious content. `yaml.load()` is documented as unsafe for untrusted input.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| `yaml.load()` with Loader | Security risk — arbitrary code execution |
| `ruamel.yaml` | Extra dependency for features we don't need (round-trip comments) |
| TOML (stdlib `tomllib`) | Config spec uses YAML, not TOML |

### Source
[PyYAML documentation](https://github.com/yaml/pyyaml): "Always use safe_load for untrusted input."

### Code Pattern
```python
import yaml

# Reading
with open("config.yml") as f:
    config = yaml.safe_load(f)

# Writing
with open("config.yml", "w") as f:
    yaml.safe_dump(config, f, default_flow_style=False)
```

---

## 2. platformdirs — Cross-Platform Directory Resolution

### Decision
Use `platformdirs` functions for all cross-platform paths:
- `user_config_dir("openreview")` for config directory
- `user_log_dir("openreview")` for log directory
- `user_data_dir("openreview")` for data/reviews directory

All with `ensure_exists=True` to auto-create directories.

### Rationale
`platformdirs` is the standard library (used by pip, black, pytest, etc.):
- Linux: `~/.config/openreview/`, `~/.local/state/openreview/log/`
- macOS: `~/Library/Application Support/openreview/`, `~/Library/Logs/openreview/`
- Windows: `C:\Users\<user>\AppData\Local\openreview\`, `C:\Users\<user>\AppData\Local\openreview\Logs\`

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| `pathlib.Path.home() / ".config"` | Does NOT map to `%APPDATA%` on Windows — wrong location |
| Manual `os.environ.get("APPDATA")` | Fragile, misses Linux/macOS handling, reinvents `platformdirs` |
| Hardcoded `~/.config/` | Excludes Windows entirely |

### Source
[platformdirs documentation](https://github.com/tox-dev/platformdirs): `user_config_dir(appname, appauthor)` with `ensure_exists=True` returns platform-appropriate path.

### Code Pattern
```python
from platformdirs import user_config_dir, user_log_dir, user_data_dir

config_path = Path(user_config_dir("openreview", ensure_exists=True))
log_path = Path(user_log_dir("openreview", ensure_exists=True))
data_path = Path(user_data_dir("openreview", ensure_exists=True))
```

---

## 3. Pydantic v2 — Configuration Validation

### Decision
Use `pydantic.BaseModel` subclasses for config.yml validation models. Handle environment variable overrides manually (no `pydantic-settings` dep).

### Rationale
Pydantic v2 is already a project dependency. Using `BaseModel` with type annotations gives us validation, default values, and `model_dump()` for serialization. We do NOT add `pydantic-settings` because:
- The env var override logic is simple (check `os.environ` for `OPENREVIEW_*` values, merge with file values)
- Avoiding the extra dep aligns with Dependency Minimalism (Principle IV)
- The override pattern is straightforward: load config → apply env vars → return merged dict

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| `pydantic-settings` `BaseSettings` | Extra dep for simple env var merge logic |
| Manual dict validation | Error-prone, no type safety |
| `dataclasses` | No built-in validation, no nested model support |
| `attrs` | Extra dep, less ergonomic than Pydantic for nested configs |

### Source
[Pydantic v2 documentation](https://github.com/pydantic/pydantic): `BaseModel` with `Field()` for validation.

### Code Pattern
```python
from pydantic import BaseModel, Field

class PrivacyConfig(BaseModel):
    tier: str = "balanced"
    strip_pii: bool = True
    log_ttl_days: int = 30

class GatewayConfig(BaseModel):
    retries: int = 2
    timeout: int = 60

class OpenReviewConfig(BaseModel):
    version: int = 1
    privacy: PrivacyConfig = PrivacyConfig()
    gateway: GatewayConfig = GatewayConfig()
```

---

## 4. Typer — CLI Subcommand Groups

### Decision
Use `app.add_typer()` for command groups. Two groups in Phase 1:
- `config` — `show`, `get <key>`, `set <key> <value>`
- `client` — `add`, `list`, `delete`

### Rationale
Typer is already a project dependency. Subcommand groups via `add_typer()` are the standard pattern:
```python
config_app = typer.Typer()
app.add_typer(config_app, name="config")

@config_app.command()
def show():
    ...

@config_app.command()
def get(key: str):
    ...
```

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| Click | Forbidden by constitution (Principle IV) |
| argparse | Much more verbose, no type hints |
| Single flat command tree | Would make `openreview config show` → `openreview-config-show` — ugly |

### Source
[Typer documentation](https://github.com/fastapi/typer): `app.add_typer(sub_app, name="config")` creates subcommand groups.

---

## 5. SQLite — Database & Migrations

### Decision
Use stdlib `sqlite3` module for all database operations. Forward-only migrations via `schema_version` table + `.sql` files.

### Rationale
SQLite is in Python's stdlib — zero dependencies. Context manager for automatic transaction commit/rollback:
```python
with sqlite3.connect("openreview.db") as conn:
    conn.execute("INSERT INTO clients VALUES (?, ?)", (id, name))
```

Forward-only migrations: a `schema_version` table stores the current version integer. On each command invocation, the app checks the version and runs any pending `.sql` migration files in order.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| SQLAlchemy | Overkill for 6 tables, adds 2+ MB, violates Principle IV |
| `alembic` | Requires SQLAlchemy, same problem |
| In-memory dicts/lists | Constitution forbids for persistent data (Principle III) |

### Source
[Python sqlite3 documentation](https://github.com/python/cpython/blob/main/Doc/library/sqlite3.rst): `sqlite3.connect()` with context manager for transactions.

### Code Pattern
```python
import sqlite3

def get_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def run_migrations(conn: sqlite3.Connection):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        num = int(migration.stem.split("_")[0])
        if num > version:
            conn.executescript(migration.read_text())
            conn.execute(f"PRAGMA user_version = {num}")
```

---

## 6. Python logging — File Handler Configuration

### Decision
Use stdlib `logging` module with `FileHandler` (log file) + `StreamHandler` (stderr). Default level INFO, DEBUG level via `--debug` flag.

### Rationale
Stdlib logging — zero dependencies. Dual output: log file for persistent debugging, stderr for real-time visibility. `platformdirs.user_log_dir()` provides the log directory path.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| `loguru` | Forbidden by constitution (Principle IV) |
| `structlog` | Forbidden by constitution (Principle IV) |
| stderr-only | No persistent log after CLI exits |

### Source
[Python logging documentation](https://github.com/python/cpython/blob/main/Doc/library/logging.rst): `logging.basicConfig(filename=..., level=...)` for simple setup, `FileHandler` + `StreamHandler` for dual output.

### Code Pattern
```python
import logging

def setup_logging(debug: bool = False, log_dir: Path = None):
    log_file = log_dir / "openreview.log"
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )
```

---

## 7. os.chmod — File Permission Handling

### Decision
On Unix: use `os.chmod(path, 0o600)` for `auth.json`. On Windows: display a warning but do not attempt to enforce permissions.

### Rationale
Python's `os.chmod` on Windows can only set the read-only flag using `stat.S_IWRITE` / `stat.S_IREAD`. All other permission bits are ignored. This is documented behavior — attempting to "enforce" permissions on Windows would be misleading.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| Windows ACL APIs (`win32security`) | Complex, fragile, breaks if pywin32 not installed, adds Windows-only code path |
| Skip permission check entirely | Loses security benefit on Unix |
| `Path.chmod(0o600)` | Same underlying `os.chmod` — no difference |

### Source
[Python os.chmod documentation](https://github.com/python/cpython/blob/main/Doc/library/os.rst): "On Windows, the `os.chmod` function can only set a file's read-only flag using `stat.S_IWRITE` and `stat.S_IREAD` constants, with all other permission bits being ignored."

### Code Pattern
```python
import os, stat, platform

def secure_auth_json(path: Path):
    if platform.system() == "Windows":
        print("Warning: auth.json contains API keys. Ensure the file is stored securely.")
        return
    current = path.stat().st_mode & 0o777
    if current != 0o600:
        print(f"Warning: auth.json has insecure permissions ({oct(current)}). Fixing...")
        path.chmod(0o600)
```
