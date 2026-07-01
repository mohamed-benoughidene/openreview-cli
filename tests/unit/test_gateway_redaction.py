from openreview_cli.gateway.redaction import RedactingFilter, redact_key


class TestRedactKey:
    def test_returns_empty_string_for_empty_key(self) -> None:
        assert redact_key("") == ""
        assert redact_key(None) == ""  # type: ignore[arg-type]

    def test_returns_all_stars_for_short_key(self) -> None:
        assert redact_key("ab") == "**"

    def test_keeps_first_four_chars_by_default(self) -> None:
        assert redact_key("abcdefgh") == "abcd****"

    def test_respects_visible_param(self) -> None:
        assert redact_key("abcdefgh", visible=2) == "ab******"

    def test_visibility_zero(self) -> None:
        assert redact_key("abcdefgh", visible=0) == "********"


class TestRedactingFilter:
    def test_redacts_matching_string_in_record(self) -> None:
        filt = RedactingFilter(["OPENAI_API_KEY"])
        import logging

        record = logging.LogRecord(
            "test", logging.INFO, "", 0, "Using OPENAI_API_KEY=sk-abc123", (), None
        )
        assert filt.filter(record)
        assert record.msg == "Using OPENAI_API_KEY****"

    def test_passes_through_clean_messages(self) -> None:
        filt = RedactingFilter(["OPENAI_API_KEY"])
        import logging

        record = logging.LogRecord("test", logging.INFO, "", 0, "Everything is fine", (), None)
        assert filt.filter(record)
        assert record.msg == "Everything is fine"

    def test_redacts_multiple_patterns(self) -> None:
        filt = RedactingFilter(["sk-", "OPENAI"])
        import logging

        record = logging.LogRecord("test", logging.INFO, "", 0, "key: sk-abc with OPENAI", (), None)
        assert filt.filter(record)
        assert "sk-****" in record.msg or "OPENAI****" in record.msg
