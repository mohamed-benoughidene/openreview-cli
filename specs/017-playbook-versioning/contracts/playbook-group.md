# CLI Contract: `openreview playbook` command group

## Purpose

Group the three playbook management commands (`import`, `list`, `show`) under a single `playbook` subcommand namespace.

## Signature

```
openreview playbook --help
openreview playbook import <yaml-path>
openreview playbook list
openreview playbook show <id> <version>
```

## Implementation in Typer

In `app.py`, define a Typer group:

```python
import typer
from openreview_cli.errors import exit_with_error, ExitCode

playbook_app = typer.Typer(
    name="playbook",
    help="Manage versioned playbooks in the local database.",
    no_args_is_help=True,
)

@playbook_app.command("import")
def playbook_import(yaml_path: Path = typer.Argument(..., help="Path to YAML playbook file")):
    """Import a YAML playbook into the local database."""
    ...

@playbook_app.command("list")
def playbook_list():
    """List all playbooks in the local database."""
    ...

@playbook_app.command("show")
def playbook_show(
    playbook_id: str = typer.Argument(..., help="Playbook ID"),
    version: int = typer.Argument(..., help="Version number"),
):
    """Show a specific playbook version from the database."""
    ...

# Register the group on the main app
app.add_typer(playbook_app)
```

## Help Output

```
$ openreview playbook --help
 Usage: openreview playbook [OPTIONS] COMMAND [ARGS]...

 Manage versioned playbooks in the local database.

 Commands:
   import  Import a YAML playbook into the local database.
   list    List all playbooks in the local database.
   show    Show a specific playbook version from the database.
```

## Exit Codes

| Command | 0 | 1 | 2 |
|---------|---|---|---|
| `import` | Imported successfully | DB/internal error | Invalid file/YAML |
| `list` | Displayed (or empty) | DB error | N/A |
| `show` | Displayed successfully | DB error | Bad ID/version |
