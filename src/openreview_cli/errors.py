import sys
from typing import NoReturn


def config_error(message: str) -> NoReturn:
    print(f"Config error: {message}", file=sys.stderr)
    sys.exit(5)


def cost_limit_error(message: str) -> NoReturn:
    print(f"Cost limit exceeded: {message}", file=sys.stderr)
    sys.exit(6)


def pii_error(message: str) -> NoReturn:
    print(f"PII error: {message}", file=sys.stderr)
    sys.exit(9)


RETRIEVAL_INDEX_NOT_FOUND = 40
RETRIEVAL_EMBEDDING_FAILED = 41
RETRIEVAL_NO_RESULTS = 42
RETRIEVAL_RERANKER_DEGRADATION = 43


def retrieval_error(message: str, code: int = RETRIEVAL_INDEX_NOT_FOUND) -> NoReturn:
    print(f"Retrieval error: {message}", file=sys.stderr)
    sys.exit(code)
