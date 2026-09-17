"""Exploratory test probes for ``feat/design-ux-remediation``.

These probes exercise new/changed features beyond the committed regression
suite: CLI argument validation, terminal report rendering edge cases, the amber
queue triage state machine, and the egress modal + cloud-call counter.  They are
kept under ``tests/exploratory/`` so the standard ``pyproject.toml`` pytest
configuration (socket isolation, timeouts, markers) applies unchanged.
"""
