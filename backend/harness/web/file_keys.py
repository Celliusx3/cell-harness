"""The settings file's keys, moved into the keyring on start; the file keeps every other value."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, JsonValue, SecretStr, TypeAdapter

from harness.config.sections import LLMSettings
from harness.config.settings import MissingConfigError
from harness.secrets import DEFAULT_MODEL_CREDENTIAL, SecretRefused, SecretService
from harness.secrets.models.details import (
    CredentialDetails,
    DiscordDetails,
    ModelDetails,
    TelegramDetails,
)

FILE_MODE = 0o600
TELEGRAM_CREDENTIAL = "telegram"
DISCORD_CREDENTIAL = "discord"

_SETTINGS_FILE = TypeAdapter(dict[str, JsonValue], config=ConfigDict(hide_input_in_errors=True))


@dataclass(frozen=True)
class KeyPlace:
    """Where the settings file holds a key."""

    section: str
    field: str


class ModelKeyInFile(BaseModel):
    """The `llm` section's key."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    api_key: str = ""


class BotTokenInFile(BaseModel):
    """A chat platform section's token."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    bot_token: str = ""


class KeysInFile(BaseModel):
    """The three keys the settings file may hold."""

    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    llm: ModelKeyInFile = ModelKeyInFile()
    telegram: BotTokenInFile = BotTokenInFile()
    discord: BotTokenInFile = BotTokenInFile()


@dataclass(frozen=True)
class KeyMove:
    """A key the settings file holds, and the credential it becomes."""

    place: KeyPlace
    credential: str
    details: CredentialDetails
    key: SecretStr


def move_file_keys(local_json: Path, llm: LLMSettings, keyring: SecretService) -> None:
    """Seal every key in `local_json` into `keyring`, then strip those keys from the file."""
    if not local_json.exists():
        return
    values = _SETTINGS_FILE.validate_json(local_json.read_text(encoding="utf-8"))
    moves = _key_moves(KeysInFile.model_validate(values), llm)
    if not moves:
        return
    for move in moves:
        _seal_key(move, keyring, local_json)
    _write_owner_only(local_json, _without_keys(values, tuple(move.place for move in moves)))


def require_default_model(keyring: SecretService, local_json: Path) -> None:
    """`MissingConfigError` saying where to put the model key when no Default model is saved."""
    if keyring.model_credential_version(DEFAULT_MODEL_CREDENTIAL) is None:
        raise MissingConfigError(
            "The keyring holds no Default model. Put its key in "
            f'{local_json} as {{"llm": {{"api_key": "…"}}}}, and the harness moves it '
            "into the keyring when it starts."
        )


def _key_moves(keys: KeysInFile, llm: LLMSettings) -> tuple[KeyMove, ...]:
    """Each key the file holds, with what it becomes; an empty one moves nothing."""
    model = _move_if_held(
        KeyPlace("llm", "api_key"),
        DEFAULT_MODEL_CREDENTIAL,
        keys.llm.api_key,
        lambda: ModelDetails(base_url=llm.base_url, model=llm.model),
    )
    telegram = _move_if_held(
        KeyPlace("telegram", "bot_token"),
        TELEGRAM_CREDENTIAL,
        keys.telegram.bot_token,
        TelegramDetails,
    )
    discord = _move_if_held(
        KeyPlace("discord", "bot_token"), DISCORD_CREDENTIAL, keys.discord.bot_token, DiscordDetails
    )
    return (*model, *telegram, *discord)


def _move_if_held(
    place: KeyPlace, credential: str, key: str, details: Callable[[], CredentialDetails]
) -> tuple[KeyMove, ...]:
    """The move of `key` at `place`, or none when it is empty; `details` is made only for a move."""
    if not key.strip():
        return ()
    return (KeyMove(place=place, credential=credential, details=details(), key=SecretStr(key)),)


def _seal_key(move: KeyMove, keyring: SecretService, local_json: Path) -> None:
    try:
        keyring.add_or_replace_key(move.credential, move.details, move.key)
    except SecretRefused as refused:
        raise MissingConfigError(
            f"{move.place.section}.{move.place.field} in {local_json} cannot move into the "
            f"keyring, so it stays in the file: {refused}. Remove or rename that credential, "
            "then start the harness again."
        ) from refused


def _without_keys(
    values: dict[str, JsonValue], places: tuple[KeyPlace, ...]
) -> dict[str, JsonValue]:
    """`values` without the keys at `places`, and without a section they leave empty."""
    stripped = {
        section: _section_without(value, frozenset(p.field for p in places if p.section == section))
        for section, value in values.items()
    }
    emptied = {place.section for place in places if stripped[place.section] == {}}
    return {section: value for section, value in stripped.items() if section not in emptied}


def _section_without(value: JsonValue, fields: frozenset[str]) -> JsonValue:
    if not isinstance(value, dict):
        return value
    return {name: item for name, item in value.items() if name not in fields}


def _write_owner_only(path: Path, values: dict[str, JsonValue]) -> None:
    """`path` replaced whole in one rename, readable by its owner alone."""
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            os.fchmod(file.fileno(), FILE_MODE)
            file.write(json.dumps(values, indent=2) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)
