"""Fixtures shared by every test.

The one thing here is a safety net, and it is here because the failure already
happened: for a while the CLI tests set `HARNESS_SESSIONS_ROOT` while the loader
had moved to `HARNESS_SESSIONS__ROOT`, so the override silently missed and a test
run wrote real conversation files into the developer's `~/.harness/sessions`.

Per-test overrides cannot prevent that — they rely on every future test
remembering. An autouse fixture can, so this redirects storage for the whole
suite and no individual test has to think about it.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_sessions(monkeypatch, tmp_path) -> None:
    """Point session storage at a throwaway directory for every test.

    Autouse and unconditional: a test that genuinely wants a different root sets
    the variable again, which wins because it runs after this.
    """
    monkeypatch.setenv("HARNESS_SESSIONS__ROOT", str(tmp_path / "sessions"))
