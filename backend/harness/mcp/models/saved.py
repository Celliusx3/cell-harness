"""A server the person set up on the MCP servers screen, as its own file keeps it."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from harness.config.sections import McpServer, named_keys, spawnable_command, usable_server_id


class ServerDraft(BaseModel):
    """How to run a server, its plain settings, and the names of the keys it needs."""

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

    @model_validator(mode="after")
    def _keys_stay_on_credentials(self) -> ServerDraft:
        """A plain setting is written to a plain file, so a key the server needs is never one."""
        if any(not name.strip() for name in self.env):
            raise ValueError("env must name each setting, none blank")
        kept = sorted(set(self.env) & set(self.needs))
        if kept:
            raise ValueError(
                f"{', '.join(kept)} is a key this server needs; save it on Credentials, "
                "not as a setting"
            )
        return self

    def server(self) -> McpServer:
        """The server to run: never required, so a failure never stops the harness."""
        return McpServer(
            command=self.command, args=self.args, env=self.env, needs=self.needs, required=False
        )


class SavedServer(ServerDraft):
    """A draft under the id its tools are named by."""

    id: str

    @field_validator("id")
    @classmethod
    def _usable(cls, value: str) -> str:
        return usable_server_id(value)


class SavedServersFile(BaseModel):
    """The servers file: every saved server, in the order each was added."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    servers: tuple[SavedServer, ...] = ()
