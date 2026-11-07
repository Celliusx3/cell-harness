"""The keys a server waits for: where they are found, and which are still missing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from pydantic import SecretStr

from harness.config.sections import McpServer


class CapabilityKeys(Protocol):
    """Where the keys saved in the app for one server are read from."""

    def capability_keys(self, server_id: str) -> Mapping[str, SecretStr]: ...


def with_saved_keys(server: McpServer, saved: Mapping[str, SecretStr]) -> McpServer:
    """`server` with `saved` over its config env: a key the person saved in the app wins."""
    unsealed = {variable: key.get_secret_value() for variable, key in saved.items()}
    return server.model_copy(update={"env": {**server.env, **unsealed}})


def missing_keys(server: McpServer) -> tuple[str, ...]:
    """Each key `server` needs that its env lacks or leaves blank, in the order it lists them."""
    return tuple(name for name in server.needs if not server.env.get(name, "").strip())
