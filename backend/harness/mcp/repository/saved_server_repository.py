"""Where the person's servers are kept: every saved server, read and replaced whole."""

from __future__ import annotations

from typing import Protocol

from harness.mcp.domain.saved import SavedServer


class SavedServerRepository(Protocol):
    """The saved servers, as storage."""

    def saved_servers(self) -> tuple[SavedServer, ...]:
        """Every saved server, in the order each was added; `()` when none is saved."""
        ...

    def replace_all(self, servers: tuple[SavedServer, ...]) -> None:
        """The saved servers replaced whole by `servers`."""
        ...
