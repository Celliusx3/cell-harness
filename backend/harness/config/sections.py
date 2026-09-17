"""The blocks of `config.json`, one model each.

Every group `Settings` nests is here, except `skills`, whose relative roots
resolve against the config file's location and so live beside the loader.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LLMSettings(BaseModel):
    """Which model answers, and how it is reached."""

    # No default: a default API key cannot exist, and a default *model* is a
    # behavioral choice — it decides what answers cost and how good they are, so
    # inheriting one silently is the "where did this come from?" bug the house
    # rules forbid. Both come from config.json or the environment.
    api_key: str = ""
    model: str = ""
    # Any OpenAI-compatible /chat/completions endpoint: OpenAI, DeepSeek,
    # Together, vLLM, Ollama.
    base_url: str = "https://api.openai.com/v1"
    # Pinned rather than omitted: leaving it unset means inheriting whatever the
    # provider currently defaults to, which can change without our code moving.
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)
    # Whole-request budget. Generous: it bounds a streaming call that may
    # legitimately think for a while, and exists so a hung connection surfaces as
    # a failed turn rather than a process that never returns.
    timeout_seconds: float = Field(default=600.0, gt=0)


class SessionSettings(BaseModel):
    """Where conversations are stored."""

    # A fixed home-relative default, never a cwd-relative one — dsh's objection
    # is that `process.cwd()` scatters logs as the working directory moves
    # (a bash call, a subprocess). `~` is expanded below so config.json can hold
    # the readable form.
    root: Path = Path.home() / ".harness" / "sessions"

    @field_validator("root")
    @classmethod
    def _expand(cls, value: Path) -> Path:
        return value.expanduser()


class TelegramSettings(BaseModel):
    """The bot to answer as, if any."""

    # Empty means the channel is off, which is the only sensible default: a token
    # cannot be guessed, and a harness that refused to start without one would be
    # unusable for everyone running it in a browser.
    bot_token: str = ""


class DiscordSettings(BaseModel):
    """The Discord bot to answer as, if any. Off when empty, as Telegram's is."""

    bot_token: str = ""


class WebSettings(BaseModel):
    """Where the browser UI is reached from *outside* this machine.

    Not the port uvicorn binds — that stays in the `Makefile`, beside the dev
    proxy that must agree with it, and is deliberately not repeated here. This
    is the address a phone is sent when a chat gets a link to an MCP App's
    page. **Empty means no such links are sent**, which is the only honest
    default: a phone cannot open `localhost`, and Telegram refuses a button
    pointing at it. Set a tunnel's `https://` URL for Telegram's Mini App
    button (it accepts nothing else), or `http://127.0.0.1:4897` for Discord
    on this machine. No trailing slash.
    """

    public_url: str = ""

    @field_validator("public_url")
    @classmethod
    def _no_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")


class CodeModeSettings(BaseModel):
    """The sandbox the model's programs run in.

    There is no `enabled`. Code mode is how this harness reaches its tools — the
    model writes a program rather than calling one tool at a time — so a switch
    would offer a second way to do the only thing there is, and `load()` refuses
    to start without the runtime rather than failing on the first script.
    """

    model_config = ConfigDict(frozen=True)

    deno_path: str = "deno"
    # Bounds one script. The tool pipeline has no timeout of its own, so without
    # this a program that loops holds the turn open until the user gives up.
    timeout_seconds: float = Field(default=60.0, gt=0)


class CompactionSettings(BaseModel):
    """When to shrink a conversation that has outgrown the model's window.

    `context_tokens` is the window in tokens. Left unset (`None`), the
    composition root asks the endpoint at startup (`GET /v1/models`); an
    endpoint that does not report one — LM Studio, say — leaves proactive
    compaction off and only the provider's own refusal triggers it. Set it to
    cap cost and latency below the real window, or to give a number the
    endpoint withholds. It is *not* a claim about the model: the reactive net
    covers a value set too high.
    """

    model_config = ConfigDict(frozen=True)

    context_tokens: int | None = Field(default=None, gt=0)


class McpServer(BaseModel):
    """One stdio MCP server, keyed in `McpSettings.servers` by its id.

    The key is also the `{id}__{tool}` namespace the model sees, so it is
    validated as a name rather than left free-form.

    `env` carries the satellite's own credentials, which is why the two config
    files deep-merge *per server*: the shape belongs in the committed
    `config.json` and only the secret in the gitignored `config.local.json`.
    """

    model_config = ConfigDict(frozen=True)

    command: str
    args: tuple[str, ...] = ()
    env: dict[str, str] = Field(default_factory=dict)

    @field_validator("command")
    @classmethod
    def _spawnable(cls, value: str) -> str:
        """A config that cannot work is a startup failure, not a silent no-op.

        `.strip()` because a blank string in JSON is a paste that went wrong —
        the same reasoning as the Telegram token guard in `web/server.py`.
        """
        if not value.strip():
            raise ValueError("command must not be blank")
        return value


class McpSettings(BaseModel):
    """Which MCP servers to connect at startup.

    Empty means no capabilities beyond the native tools, which is the only
    sensible default: a server is a command on *this* machine and cannot be
    guessed.
    """

    servers: dict[str, McpServer] = Field(default_factory=dict)

    @field_validator("servers")
    @classmethod
    def _usable_ids(cls, value: dict[str, McpServer]) -> dict[str, McpServer]:
        """Ids must survive being half of a tool name, and half of an identifier.

        No underscore, so the `{server}__{tool}` split stays unambiguous. And
        nothing outside `[a-z0-9]`, for two reasons: a provider cannot reject the
        whole request — one bad name fails *every* tool in it, not just this
        server's — and code mode prints each tool as `declare function
        {name}(...)` **unquoted** (`tools/native/code/typescript.py`), so a
        hyphen produced `declare function my-server__do_thing(...)`, which is not
        parseable TypeScript. The model would then write a call the sandbox
        cannot resolve, with nothing pointing at the id as the cause.

        Hyphens were permitted here until that was found. Refusing at load is the
        only place it can be said clearly, because by the time the printer sees
        the name there is no id left to blame.
        """
        for name in value:
            if not _SERVER_ID.match(name):
                raise ValueError(
                    f"{name!r} is not a usable MCP server id: a lowercase letter followed "
                    "by lowercase letters or digits, at most 32. No underscore, because it "
                    "would make the {server}__{tool} split ambiguous; no hyphen and no "
                    "leading digit, because {server}__{tool} becomes a TypeScript identifier "
                    "in code mode"
                )
        return value


# Must *start* with a letter, not merely consist of letters and digits: the id
# is the first thing in the printed identifier, so `3d` would emit
# `declare function 3d__render(...)`. Found by a test asserting the property
# directly rather than trusting the character class.
_SERVER_ID = re.compile(r"^[a-z][a-z0-9]{0,31}$")
