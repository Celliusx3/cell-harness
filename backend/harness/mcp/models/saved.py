"""A server the person set up on the MCP servers screen, as typed and as its own file keeps it."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator, model_validator

from harness.config.sections import McpServer, named_keys, spawnable_command, usable_server_id


class ServerCommand(BaseModel):
    """How to run a server, its env, and the names of the keys it needs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    command: str
    args: tuple[str, ...]
    env: dict[str, str]
    needs: tuple[str, ...]

    @field_validator("command")
    @classmethod
    def _spawnable(cls, value: str) -> str:
        return spawnable_command(value)

    @field_validator("needs")
    @classmethod
    def _named(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return named_keys(value)

    @field_validator("env")
    @classmethod
    def _named_settings(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not name.strip() for name in value):
            raise ValueError("env must name each setting, none blank")
        return value


class ServerDraft(ServerCommand):
    """A server as the screen sends it: plain settings in `env`; a key not in `keys` is kept."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    keys: dict[str, SecretStr]

    @model_validator(mode="after")
    def _keys_apart_from_settings(self) -> ServerDraft:
        """A key goes in `keys`, hidden; a plain setting in `env` is never one the server needs."""
        kept = sorted(set(self.env) & set(self.needs))
        if kept:
            raise ValueError(
                f"{', '.join(kept)} is a key this server needs; type it as a key, not as a setting"
            )
        unneeded = sorted(set(self.keys) - set(self.needs))
        if unneeded:
            raise ValueError(f"{', '.join(unneeded)} is not a key this server needs")
        blank = sorted(
            name for name, key in self.keys.items() if not key.get_secret_value().strip()
        )
        if blank:
            raise ValueError(f"{', '.join(blank)} is blank; leave a key out to keep the one saved")
        return self

    def saved(self, server_id: str, kept: Mapping[str, str]) -> SavedServer:
        """The server to save as `server_id`: each key typed, else its value in `kept`, if any."""
        held = {name: kept[name] for name in self.needs if name in kept}
        typed = {name: key.get_secret_value() for name, key in self.keys.items()}
        return SavedServer(
            id=server_id,
            command=self.command,
            args=self.args,
            env={**self.env, **held, **typed},
            needs=self.needs,
        )


class NewServer(ServerDraft):
    """A draft under the id its tools will be named by."""

    id: str

    @field_validator("id")
    @classmethod
    def _usable(cls, value: str) -> str:
        return usable_server_id(value)


class SavedServer(ServerCommand):
    """A saved server under its id, with the values of its keys in its env."""

    id: str

    @field_validator("id")
    @classmethod
    def _usable(cls, value: str) -> str:
        return usable_server_id(value)

    def server(self) -> McpServer:
        """The server to run, its keys in its env."""
        return McpServer(command=self.command, args=self.args, env=self.env, needs=self.needs)


class SavedServersFile(BaseModel):
    """The servers file: every saved server, in the order each was added."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    servers: tuple[SavedServer, ...] = ()
