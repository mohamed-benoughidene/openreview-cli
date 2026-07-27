.PHONY: test test-fast test-offline test-slow test-memory

test: test-offline test-memory
	@echo "=== All suites passed ==="

test-fast:
	uv run pytest -m "fast" -q

test-offline:
	uv run pytest -m "fast or slow" -q

test-slow:
	uv run pytest -m slow -v --reruns 1

test-memory:
	uv run pytest -m memory -q
