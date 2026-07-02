from openreview_cli.prompts.variables import substitute


class TestVariableSubstitution:
    def test_substitute_single_variable(self) -> None:
        result = substitute("Extract {clause_count} clauses.", "extraction", {"clause_count": "42"})
        assert result == "Extract 42 clauses."

    def test_substitute_multiple_variables(self) -> None:
        result = substitute(
            "Extract {clause_count} from {document_type}.",
            "extraction",
            {"clause_count": "10", "document_type": "the contract"},
        )
        assert result == "Extract 10 from the contract."

    def test_substitute_unknown_variable_left_as_is(self) -> None:
        result = substitute("Hello {unknown_var}", "extraction", {})
        assert result == "Hello {unknown_var}"

    def test_substitute_no_variables(self) -> None:
        result = substitute("Hello world", "extraction", {"ignored": "value"})
        assert result == "Hello world"

    def test_substitute_empty_content(self) -> None:
        result = substitute("", "extraction", {"key": "value"})
        assert result == ""

    def test_substitute_per_slot_variable_sets(self) -> None:
        result = substitute(
            "Extract {clause_count} from {document_type}.",
            "extraction",
            {"clause_count": "5", "document_type": "NDA"},
        )
        assert result == "Extract 5 from NDA."

    def test_substitute_variable_with_special_chars(self) -> None:
        result = substitute("{key}", "extraction", {"key": "value with spaces"})
        assert result == "value with spaces"

    def test_substitute_repeated_variable(self) -> None:
        result = substitute("{x} and {x}", "extraction", {"x": "same"})
        assert result == "same and same"
