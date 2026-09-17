"""Central exit-code registry and error helpers.

Every CLI command and library entry point that terminates the process MUST
import its exit code from here so the codes stay consistent and documented.
``fail`` is the single primitive; every specialised helper delegates to it and
keeps the printed prefix and numeric code stable.
"""

import sys
from typing import NoReturn

# ── Canonical exit codes (single source of truth) ────────────────────────
EXIT_SUCCESS = 0  # success
EXIT_USER_ERROR = 1  # missing/invalid file, bad path, unsupported input
EXIT_USAGE = 2  # CLI usage / flag-value validation error
EXIT_NOT_FOUND = 3  # requested resource does not exist
EXIT_GATEWAY = 4  # model-gateway / provider failure
EXIT_CONFIG = 5  # configuration problem
EXIT_COST_LIMIT = 6  # cost limit reached
EXIT_PARSE_ERROR = 8  # document parse failure
EXIT_PII = 9  # PII processing failure
EXIT_RETRIEVAL_INDEX_NOT_FOUND = 40
EXIT_RETRIEVAL_INDEX_CORRUPT = 41
EXIT_RETRIEVAL_INDEX_OUTDATED = 42
EXIT_RETRIEVAL_DIM_MISMATCH = 43
EXIT_BENCHMARK_REGRESSION = 75
EXIT_BENCHMARK_CONFIG = 78


def fail(message: str, code: int, *, prefix: str = "Error") -> NoReturn:
    """Print ``prefix: message`` to stderr and exit with ``code``."""
    print(f"{prefix}: {message}", file=sys.stderr)
    raise SystemExit(code)


def usage_error(message: str) -> NoReturn:
    """Exit 2 after reporting a CLI usage or flag-value validation error."""
    fail(message, EXIT_USAGE)


def parse_error(message: str) -> NoReturn:
    """Exit 8 after reporting a document parse failure."""
    fail(message, EXIT_PARSE_ERROR, prefix="Parse error")


def config_error(message: str) -> NoReturn:
    """Exit 5 after reporting a configuration problem."""
    fail(message, EXIT_CONFIG, prefix="Config error")


def cost_limit_error(message: str) -> NoReturn:
    """Exit 6 after reporting that a cost limit was reached."""
    fail(message, EXIT_COST_LIMIT, prefix="Cost limit exceeded")


def pii_error(message: str) -> NoReturn:
    """Exit 9 after reporting a PII processing failure."""
    fail(message, EXIT_PII, prefix="PII error")


def retrieval_error(message: str, code: int = EXIT_RETRIEVAL_INDEX_NOT_FOUND) -> NoReturn:
    """Exit with a retrieval error code (default: index not found, 40)."""
    fail(message, code, prefix="Retrieval error")
