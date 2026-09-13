"""Settings: two JSON files, one committed and one not.

Loading priority, highest wins — syndesis's layering, with its `.env` folded into
a second JSON file so there is only one format to know:

    1. constructor kwargs          (tests, explicit composition)
    2. environment variables       HARNESS_LLM__MODEL=…
    3. `config.local.json`         gitignored: secrets and local overrides
    4. `config.json`               committed: how the harness runs by default

The two JSON files have the **same shape**, so overriding something is copying
its block and changing the value — no translation between a nested document and
flat `SCREAMING__SNAKE` names. That translation is the only reason a `.env` would
still be here; without it, `.env` is a second format for the same job.

Environment variables remain, because that is how CI and containers inject
configuration — nothing reads a file there. They nest with `__`
(`HARNESS_LLM__API_KEY`), and the `HARNESS_` prefix is deliberate: a harness that
picked up a bare `LLM__API_KEY` from someone's shell would be a surprising thing
to debug.

**One `Settings`, not one class per concern.** Nested groups mean `settings.llm`
and `settings.sessions` come from one object loaded once. Two independent
`BaseSettings` would each parse the files separately and give "where does this
value come from?" two answers — the failure mode the house rules name.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# backend/harness/config/settings.py → backend/
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_JSON = Path(os.getenv("HARNESS_CONFIG", _BACKEND_ROOT / "config.json"))
# Optional. A fresh clone has none, and every value it would hold has either a
# default or a loud error naming it.
_LOCAL_JSON = _CONFIG_JSON.with_name(_CONFIG_JSON.stem + ".local" + _CONFIG_JSON.suffix)


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


class SkillSettings(BaseModel):
    """Where skills are read from, in rank order, and where the editor writes.

    `.agents/skills` is the cross-client convention (agentskills.io): a skill
    installed by any other tool is visible here, and one saved from our settings
    page is visible to them. The project copy outranks the home copy, so a
    repository can pin its own version of a skill.

    Relative roots resolve against the project: the nearest `.git` ancestor of
    the config file, or the backend's parent when there is none.
    """

    model_config = ConfigDict(frozen=True)

    roots: tuple[Path, ...] = (Path(".agents/skills"), Path("~/.agents/skills"))
    editable: Path = Path("~/.agents/skills")

    @field_validator("roots", "editable")
    @classmethod
    def _resolve(cls, value: Path | tuple[Path, ...]) -> Path | tuple[Path, ...]:
        if isinstance(value, tuple):
            return tuple(_project_path(path) for path in value)
        return _project_path(value)

    @model_validator(mode="after")
    def _editable_is_read(self) -> SkillSettings:
        """A root nobody reads from is where 7.5's inert grant came from: the
        page would write a skill and the model would never see it."""
        if self.editable not in self.roots:
            raise ValueError(
                f"skills.editable {str(self.editable)!r} must be one of skills.roots, "
                "or what the editor saves is never read"
            )
        return self


def _project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else _project_root() / expanded


def _project_root() -> Path:
    for candidate in (_CONFIG_JSON.parent, *_CONFIG_JSON.parent.parents):
        if (candidate / ".git").exists():
            return candidate
    return _BACKEND_ROOT.parent


# Must *start* with a letter, not merely consist of letters and digits: the id
# is the first thing in the printed identifier, so `3d` would emit
# `declare function 3d__render(...)`. Found by a test asserting the property
# directly rather than trusting the character class.
_SERVER_ID = re.compile(r"^[a-z][a-z0-9]{0,31}$")


class Settings(BaseSettings):
    """Everything the harness is configured with, loaded once."""

    model_config = SettingsConfigDict(
        env_prefix="HARNESS_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
    )

    llm: LLMSettings = Field(default_factory=LLMSettings)
    sessions: SessionSettings = Field(default_factory=SessionSettings)
    telegram: TelegramSettings = Field(default_factory=TelegramSettings)
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    code: CodeModeSettings = Field(default_factory=CodeModeSettings)
    mcp: McpSettings = Field(default_factory=McpSettings)
    skills: SkillSettings = Field(default_factory=SkillSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Highest priority first. `config.json` is last, so it is the floor
        every other source overrides rather than a thing that overrides them.

        A missing file contributes nothing rather than failing, which is what
        lets `config.local.json` be optional and `config.json` be absent in a
        deployment configured entirely through the environment.
        """
        return (
            init_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_LOCAL_JSON),
            JsonConfigSettingsSource(settings_cls, json_file=_CONFIG_JSON),
        )


class MissingConfigError(RuntimeError):
    """A value with no possible default was not supplied anywhere."""


def load() -> Settings:
    """Settings for a real run, with the two unguessable values checked.

    Validated here rather than as required fields, because a required field
    would make `Settings()` unusable in the many tests that do not care about a
    model — and because the error a caller wants names the file to edit, not a
    pydantic field path.
    """
    settings = Settings()
    if shutil.which(settings.code.deno_path) is None:
        raise MissingConfigError(
            f"{settings.code.deno_path!r} is not on PATH, and the harness runs "
            "every tool call through a Deno sandbox. Install Deno "
            f"(https://deno.com) or set code.deno_path in {_CONFIG_JSON}."
        )
    missing = [
        name
        for name, value in (("model", settings.llm.model), ("api_key", settings.llm.api_key))
        if not value.strip()
    ]
    if missing:
        names = " and ".join(f"llm.{name}" for name in missing)
        verb = "is" if len(missing) == 1 else "are"
        raise MissingConfigError(
            f"{names} {verb} not set. Non-secret values belong in {_CONFIG_JSON}; "
            f"the API key belongs in {_LOCAL_JSON} (gitignored) as "
            f'{{"llm": {{"api_key": "…"}}}}, or in HARNESS_LLM__API_KEY.'
        )
    return settings
