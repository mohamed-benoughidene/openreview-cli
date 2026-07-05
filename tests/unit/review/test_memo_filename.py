"""Unit tests for memo filename generation and output directory resolution."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openreview_cli.review.memo.filename import (
    DEFAULT_OUTPUT_DIR,
    deduplicate,
    generate_filename,
    resolve_output_dir,
    sanitize_stem,
)
from openreview_cli.review.memo.models import MemoFormat


class TestSanitizeStem:
    def test_lowercases(self) -> None:
        assert sanitize_stem("NDA Agreement") == "nda-agreement"

    def test_spaces_to_hyphens(self) -> None:
        assert sanitize_stem("my contract doc") == "my-contract-doc"

    def test_removes_special_chars(self) -> None:
        assert sanitize_stem("hello!@#world") == "helloworld"

    def test_keeps_hyphens_and_underscores(self) -> None:
        assert sanitize_stem("my-doc_v2") == "my-doc_v2"

    def test_collapses_multiple_hyphens(self) -> None:
        assert sanitize_stem("a---b") == "a-b"

    def test_strips_leading_trailing_hyphens(self) -> None:
        assert sanitize_stem("-hello-") == "hello"

    def test_empty_string_falls_back(self) -> None:
        assert sanitize_stem("") == "document"

    def test_only_special_chars_falls_back(self) -> None:
        assert sanitize_stem("@#$%^") == "document"

    def test_handles_unicode(self) -> None:
        assert sanitize_stem("café-con-leche") == "caf-con-leche"


class TestGenerateFilename:
    def test_markdown_format(self) -> None:
        name = generate_filename("precheck", "nda", MemoFormat.MARKDOWN)
        assert name.endswith(".md")
        assert name.startswith("precheck-nda-")
        # Timestamp format YYYYMMDD-HHMMSS
        parts = name.replace(".md", "").split("-")
        assert len(parts) >= 3
        assert parts[0] == "precheck"
        assert parts[1] == "nda"

    def test_json_format(self) -> None:
        name = generate_filename("dealcheck", "merger agreement", MemoFormat.JSON)
        assert name.endswith(".json")
        assert name.startswith("dealcheck-merger-agreement-")

    def test_docx_format(self) -> None:
        name = generate_filename("hirecheck", "contract", MemoFormat.DOCX)
        assert name.endswith(".docx")
        assert name.startswith("hirecheck-contract-")

    def test_mode_prefix(self) -> None:
        for mode in ("precheck", "dealcheck", "hirecheck"):
            name = generate_filename(mode, "doc", MemoFormat.MARKDOWN)
            assert name.startswith(f"{mode}-doc-")

    def test_timestamp_format(self) -> None:
        import re

        name = generate_filename("precheck", "doc", MemoFormat.MARKDOWN)
        stem = name.replace(".md", "")
        # Extract timestamp (last 2 segments mode-stem-YYYYMMDD-HHMMSS)
        segments = stem.split("-")
        ts = segments[-2] + "-" + segments[-1]
        assert re.match(r"^\d{8}-\d{6}$", ts), (
            f"Timestamp {ts} doesn't match pattern (segments: {segments})"
        )


class TestResolveOutputDir:
    def test_default_dir(self) -> None:
        result = resolve_output_dir(None)
        assert result == DEFAULT_OUTPUT_DIR

    def test_creates_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "new-subdir" / "nested"
            assert not new_dir.exists()
            result = resolve_output_dir(new_dir)
            assert result == new_dir
            assert new_dir.is_dir()

    def test_rejects_file_path(self) -> None:
        with tempfile.NamedTemporaryFile() as f:
            path = Path(f.name)
            with pytest.raises(ValueError, match="not a directory"):
                resolve_output_dir(path)


class TestDeduplicate:
    def test_file_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.md"
            result = deduplicate(path)
            assert result == path

    def test_appends_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.md"
            path.write_text("original")
            result = deduplicate(path)
            assert result == Path(tmp) / "test-1.md"
            assert not result.exists()

    def test_appends_incrementing_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p0 = Path(tmp) / "test.md"
            p0.write_text("original")
            p1 = Path(tmp) / "test-1.md"
            p1.write_text("first")
            result = deduplicate(Path(tmp) / "test.md")
            assert result == Path(tmp) / "test-2.md"

    def test_preserves_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            path.write_text("{}")
            result = deduplicate(path)
            assert result.suffix == ".json"
            assert result.stem == "report-1"
