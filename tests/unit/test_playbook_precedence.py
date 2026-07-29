"""Unit tests for playbook precedence — T007 through T013.

Tests that when both ``--playbook`` (DB playbook ID) and ``--playbook-path``
(filesystem path) are provided to ``precheck review``, a warning is emitted
and the DB playbook takes precedence (T007-T009). Also tests that each of the
three loader paths — DB, file, bundled — is correctly dispatched when only the
corresponding argument is provided (T010-T013).
"""

from __future__ import annotations

import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

from openreview_cli.review import run_review

# ── helpers ──


def _make_mock_playbook(**kwargs: object) -> MagicMock:
    """Return a minimal mock playbook with an ``id`` attribute."""
    pb = MagicMock()
    pb.id = kwargs.get("id", "mock-pb")
    return pb


def _make_mock_review_command(playbook: MagicMock) -> MagicMock:
    """Return a mock ReviewCommand whose pipe() returns a dummy pipeline."""
    cmd = MagicMock()
    cmd.pipeline = MagicMock()
    cmd.pipeline.run.return_value = []
    return cmd


# ════════════════════════════════════════════════
# T007, T008, T009: Warning emission
# ════════════════════════════════════════════════


class TestPlaybookPrecedenceWarning:
    """UserWarning emitted when both ``playbook_id`` and ``playbook_path`` are given."""

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_warning_emitted_when_both_provided(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T007: UserWarning is emitted when both --playbook and --playbook-path given."""
        mock_db.return_value = (_make_mock_playbook(id="db-playbook"), 1)
        mock_cmd.side_effect = _make_mock_review_command
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run_review(
                paths=["doc.pdf"],
                playbook_id="db-playbook",
                playbook_path="/some/path.yaml",
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) >= 1, "Expected at least one UserWarning"

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_warning_message_content(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T008: Warning message states --playbook takes precedence over --playbook-path."""
        mock_db.return_value = (_make_mock_playbook(id="db-playbook"), 2)
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run_review(
                paths=["doc.pdf"],
                playbook_id="db-playbook",
                playbook_path="/some/path.yaml",
            )

        messages = [str(x.message) for x in w if issubclass(x.category, UserWarning)]
        assert any("--playbook" in m and "precedence" in m for m in messages), (
            f"Warning message should mention --playbook and precedence; got {messages}"
        )

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_no_warning_when_only_playbook_id(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """No warning when only --playbook is provided without --playbook-path."""
        mock_db.return_value = (_make_mock_playbook(id="db-playbook"), 1)
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run_review(
                paths=["doc.pdf"],
                playbook_id="db-playbook",
                playbook_path=None,
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0, (
            f"Expected no UserWarning when only playbook_id given; got {len(user_warnings)}"
        )

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_no_warning_when_only_playbook_path(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """No warning when only --playbook-path is provided without --playbook."""
        mock_load.return_value = _make_mock_playbook(id="file-playbook")
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run_review(
                paths=["doc.pdf"],
                playbook_id=None,
                playbook_path="/some/path.yaml",
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0, (
            f"Expected no UserWarning when only playbook_path given; got {len(user_warnings)}"
        )

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_no_warning_when_neither_provided(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """No warning when neither --playbook nor --playbook-path is given (bundled default)."""
        mock_bundled.return_value = _make_mock_playbook(id="precheck-nda-v1")
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            run_review(
                paths=["doc.pdf"],
                playbook_id=None,
                playbook_path=None,
            )

        user_warnings = [x for x in w if issubclass(x.category, UserWarning)]
        assert len(user_warnings) == 0, (
            f"Expected no UserWarning when neither flag given; got {len(user_warnings)}"
        )


# ════════════════════════════════════════════════
# T010, T011, T012, T013: Precedence behavior
# ════════════════════════════════════════════════


class TestPlaybookPrecedenceBehavior:
    """When both flags are given the DB loader is called and the file loader is not."""

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_db_playbook_takes_precedence_over_path(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T010: When both provided, DB loader is called; file + bundled loaders are not."""
        mock_db.return_value = (_make_mock_playbook(id="db-playbook"), 1)
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            run_review(
                paths=["doc.pdf"],
                playbook_id="db-playbook",
                playbook_path="/some/path.yaml",
            )

        mock_db.assert_called_once_with("db-playbook")
        mock_load.assert_not_called()
        mock_bundled.assert_not_called()

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_only_path_calls_file_loader(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T011: When only --playbook-path, file loader is called; DB + bundled are not."""
        mock_load.return_value = _make_mock_playbook(id="file-playbook")
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            run_review(
                paths=["doc.pdf"],
                playbook_id=None,
                playbook_path="/custom/pb.yaml",
            )

        mock_load.assert_called_once()
        # Verify the path argument is a Path object wrapping the string
        call_arg = mock_load.call_args[0][0]
        assert isinstance(call_arg, Path)
        assert str(call_arg) == "/custom/pb.yaml"
        mock_db.assert_not_called()
        mock_bundled.assert_not_called()

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_only_id_calls_db_loader(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T012: When only --playbook, DB loader is called; file + bundled are not."""
        mock_db.return_value = (_make_mock_playbook(id="db-playbook"), 1)
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            run_review(
                paths=["doc.pdf"],
                playbook_id="my-pb",
                playbook_path=None,
            )

        mock_db.assert_called_once_with("my-pb")
        mock_load.assert_not_called()
        mock_bundled.assert_not_called()

    @patch("openreview_cli.review.runner.load_playbook_from_db")
    @patch("openreview_cli.review.runner.load_playbook")
    @patch("openreview_cli.review.runner.load_bundled")
    @patch("openreview_cli.review.ReviewCommand")
    def test_neither_calls_bundled_loader(
        self,
        mock_cmd: MagicMock,
        mock_bundled: MagicMock,
        mock_load: MagicMock,
        mock_db: MagicMock,
    ) -> None:
        """T013: When neither given, bundled loader is called; DB + file are not."""
        mock_bundled.return_value = _make_mock_playbook(id="precheck-nda-v1")
        cmd_instance = _make_mock_review_command(_make_mock_playbook())
        mock_cmd.return_value = cmd_instance

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            run_review(
                paths=["doc.pdf"],
                playbook_id=None,
                playbook_path=None,
            )

        mock_bundled.assert_called_once_with()
        mock_db.assert_not_called()
        mock_load.assert_not_called()
