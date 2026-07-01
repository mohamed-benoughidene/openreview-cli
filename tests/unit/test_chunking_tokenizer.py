from openreview_cli.chunking.tokenizer import count_tokens, split_tokens


def test_count_tokens_empty() -> None:
    assert count_tokens("") == 0


def test_count_tokens_whitespace_only() -> None:
    assert count_tokens("   \n  \t  ") == 0


def test_count_tokens_simple() -> None:
    assert count_tokens("hello world") == 2


def test_count_tokens_with_punctuation() -> None:
    assert count_tokens("hello, world!") == 4  # hello , world !


def test_split_tokens_first_two() -> None:
    text = "hello world foo bar"
    tokens = split_tokens(text, 0, 2)
    assert len(tokens) == 2
    assert tokens[0][0] == "hello"
    assert tokens[1][0] == "world"


def test_split_tokens_middle() -> None:
    text = "hello world foo bar"
    tokens = split_tokens(text, 1, 3)
    assert len(tokens) == 2
    assert tokens[0][0] == "world"
    assert tokens[1][0] == "foo"


def test_split_tokens_beyond_end() -> None:
    text = "hello world"
    tokens = split_tokens(text, 0, 999)
    assert len(tokens) == 2
