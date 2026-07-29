"""compute_config_hash — canonical JSON + SHA-256."""

from __future__ import annotations

from openreview_cli.pii.config_hash import compute_config_hash


def test_deterministic() -> None:
    cfg: dict[str, object] = {"threshold": 0.7, "entities": ["PERSON", "EMAIL"]}
    assert compute_config_hash(cfg) == compute_config_hash(dict(cfg))


def test_key_order_independent() -> None:
    a: dict[str, object] = {"x": 1, "y": [1, 2], "z": {"n": True}}
    b: dict[str, object] = {"z": {"n": True}, "y": [1, 2], "x": 1}
    assert compute_config_hash(a) == compute_config_hash(b)


def test_value_change_changes_hash() -> None:
    a: dict[str, object] = {"threshold": 0.7}
    assert compute_config_hash(a) != compute_config_hash({"threshold": 0.8})


def test_hex_sha256_shape() -> None:
    h = compute_config_hash({"a": 1})
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)
