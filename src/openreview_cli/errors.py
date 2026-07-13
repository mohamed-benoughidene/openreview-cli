import sys
from typing import NoReturn

# ── Exit codes per FR-031 ────────────────────────────────────────────────────
# 1 = user error (invalid input, missing args)
# 2 = config error (missing/invalid config, schema violation)
# 3 = provider error (API failure, auth failure, rate limit)

EXIT_USER_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_PROVIDER_ERROR = 3

# Legacy exit codes (kept for backward compat — existing commands unchanged)
EXIT_LEGACY_CONFIG_ERROR = 5
EXIT_LEGACY_COST_LIMIT = 6
EXIT_LEGACY_PARSE_ERROR = 8
EXIT_LEGACY_PII_ERROR = 9

RETRIEVAL_INDEX_NOT_FOUND = 40
RETRIEVAL_EMBEDDING_FAILED = 41
RETRIEVAL_NO_RESULTS = 42
RETRIEVAL_RERANKER_DEGRADATION = 43


def config_error(message: str) -> NoReturn:
    """Config error — exits with code 2 (FR-031)."""
    print(f"Config error: {message}", file=sys.stderr)
    sys.exit(EXIT_CONFIG_ERROR)


def cost_limit_error(message: str) -> NoReturn:
    print(f"Cost limit exceeded: {message}", file=sys.stderr)
    sys.exit(EXIT_LEGACY_COST_LIMIT)


def pii_error(message: str) -> NoReturn:
    print(f"PII error: {message}", file=sys.stderr)
    sys.exit(EXIT_LEGACY_PII_ERROR)


def retrieval_error(message: str, code: int = RETRIEVAL_INDEX_NOT_FOUND) -> NoReturn:
    print(f"Retrieval error: {message}", file=sys.stderr)
    sys.exit(code)
