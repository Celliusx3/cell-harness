"""Fixtures shared by every test."""

from __future__ import annotations

import pytest

from harness.config import settings as settings_module


@pytest.fixture(autouse=True)
def _isolate_sessions(monkeypatch, tmp_path) -> None:
    """Point session storage at a throwaway directory for every test."""
    monkeypatch.setenv("HARNESS_SESSIONS__ROOT", str(tmp_path / "sessions"))


@pytest.fixture(autouse=True)
def _isolate_local_settings(monkeypatch, tmp_path) -> None:
    """Point the per-machine settings file at a throwaway path."""
    monkeypatch.setattr(settings_module, "_LOCAL_JSON", tmp_path / "config.local.json")
