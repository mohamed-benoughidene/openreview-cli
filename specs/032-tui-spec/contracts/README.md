# Interface Contracts: TUI

This directory documents the public interface contracts of the TUI feature.

## What's documented

- `cli-dispatch.md` — what happens when `openreview` is invoked with various argument combinations
- `tui-events.md` — key events the TUI publishes (e.g., review completed, gateway updated)

## Why contracts matter

The TUI is a presentation layer. It does NOT define new public APIs to the outside world; all existing CLI subcommands retain their existing contracts. The contracts documented here describe the TUI's INTERNAL contracts with the existing domain layer and with the OS (TTY, environment variables, signal handling).
