<p align="center">
  <img src="assets/logo.png" alt="openreview logo" width="200">
</p>

# openreview-cli

[![CI](https://github.com/mohamed-benoughidene/openreview-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/mohamed-benoughidene/openreview-cli/actions/workflows/ci.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](.python-version)

Privacy-first contract review tool. Reads contract files, compares them against a custom playbook, and produces a structured memo of what matches and what doesn't.

## Status

Pre-alpha. The package is not yet on PyPI. APIs and the underlying spec are preliminary and will change.

## Installation

```bash
uv tool install openreview-cli
```

> Not yet on PyPI. The command above documents the intended install path. Today the only way to run the tool is from a checkout:

```bash
git clone https://github.com/mohamed-benoughidene/openreview-cli
cd openreview-cli
git submodule update --init
uv sync
uv run python main.py
```

## Quick start

```bash
openreview --help
openreview gateway setup                         # Configure AI providers
openreview playbook create --client <name>       # Set up a client playbook
openreview precheck review contract.pdf --client <name>
```

## Contributing

By contributing, you agree to the [CLA](CLA.md). All contributions are subject to the project's [Code of Conduct](.github/CODE_OF_CONDUCT.md). Bug reports and feature requests use the templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/).

## License

Dual-licensed:

- [GNU Affero General Public License v3.0](LICENSE) (AGPL-3.0)
- [Commercial License](COMMERCIAL_LICENSE.md) — for organizations that want to avoid AGPL-3.0's source-disclosure obligations

See [NOTICE.md](NOTICE.md) for trademarks and licensing details.

## Contact

- Issues: [GitHub Issues](https://github.com/mohamed-benoughidene/openreview-cli/issues)
- Twitter: [@mohamedbeno22](https://x.com/mohamedbeno22)
