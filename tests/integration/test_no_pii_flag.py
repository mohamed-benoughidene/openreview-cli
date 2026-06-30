"""Integration tests for the --no-pii flag.

Verifies that --no-pii disables PII stripping, processes raw text,
creates no encrypted mapping, logs a warning, and sets entity_count=0.
"""

from tests.integration.test_precheck_pii import TestPrecheckPii

TestPrecheckNoPii = TestPrecheckPii
