"""Fixtures shared by every test."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_sessions(monkeypatch, tmp_path) -> None:
    """Point session storage at a throwaway directory for every test."""
    monkeypatch.setenv("HARNESS_SESSIONS__ROOT", str(tmp_path / "sessions"))
