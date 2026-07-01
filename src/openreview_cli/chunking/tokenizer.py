import re

_TOKEN_SPLIT_RE = re.compile(r"\w+|[^\w\s]")


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_TOKEN_SPLIT_RE.findall(text))


def split_tokens(text: str, start: int, end: int) -> list[tuple[str, int, int]]:
    tokens = list(_TOKEN_SPLIT_RE.finditer(text))
    selected = tokens[start:end]
    return [(m.group(), m.start(), m.end()) for m in selected]
