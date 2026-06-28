import sys
from typing import NoReturn

sys.tracebacklimit = 0

SUCCESS = 0
GENERAL_ERROR = 1
USAGE_ERROR = 2
CONFIG_ERROR = 3
INPUT_ERROR = 4
NETWORK_ERROR = 5


def config_error(message: str) -> NoReturn:
    print(f"Config error: {message}", file=sys.stderr)
    sys.exit(5)


def cost_limit_error(message: str) -> NoReturn:
    print(f"Cost limit exceeded: {message}", file=sys.stderr)
    sys.exit(6)


def pii_error(message: str) -> NoReturn:
    print(f"PII error: {message}", file=sys.stderr)
    sys.exit(9)


def gateway_error(message: str, slot: str | None = None) -> NoReturn:
    print(f"Gateway error: {message}", file=sys.stderr)
    if slot:
        print(f"Slot: {slot}", file=sys.stderr)
    sys.exit(7)
