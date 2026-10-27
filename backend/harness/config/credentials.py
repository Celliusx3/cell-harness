"""The harness's own keys, read from its settings and shown only by their last four characters."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.fields import FieldInfo

from harness.config.settings import Settings

SECRET = "x-secret"
READ_ONLY = "x-readonly"
REQUIRED = "x-required"
ENV_PREFIX = "HARNESS_"
ENV_NESTING = "__"
SHOWN_CHARACTERS = 4
MASKABLE_LENGTH = 8


class Credential(BaseModel):
    """One key the harness holds, as a page may see it: whether it is set, never its value."""

    model_config = ConfigDict(frozen=True)

    path: str
    section: str
    description: str
    is_set: bool
    required: bool
    last_four: str | None
    set_by_env: str | None


def credentials(settings: Settings, env: Mapping[str, str]) -> tuple[Credential, ...]:
    """Every secret a person sets, in the settings' own order."""
    return tuple(
        _credential(section_name, name, str(getattr(section, name)), field, env)
        for section_name, section in _sections(settings)
        for name, field in type(section).model_fields.items()
        if _is_settable_secret(field)
    )


def _sections(settings: Settings) -> list[tuple[str, BaseModel]]:
    values = ((name, getattr(settings, name)) for name in type(settings).model_fields)
    return [(name, value) for name, value in values if isinstance(value, BaseModel)]


def _is_settable_secret(field: FieldInfo) -> bool:
    extra = _markers(field)
    return bool(extra.get(SECRET)) and not extra.get(READ_ONLY)


def _markers(field: FieldInfo) -> dict[str, object]:
    return dict(field.json_schema_extra) if isinstance(field.json_schema_extra, dict) else {}


def _credential(
    section: str, name: str, value: str, field: FieldInfo, env: Mapping[str, str]
) -> Credential:
    is_set = value.strip() != ""
    return Credential(
        path=f"{section}.{name}",
        section=section,
        description=field.description or "",
        is_set=is_set,
        required=bool(_markers(field).get(REQUIRED)),
        last_four=value[-SHOWN_CHARACTERS:] if is_set and len(value) >= MASKABLE_LENGTH else None,
        set_by_env=_variable_setting(section, name, env),
    )


def _variable_setting(section: str, name: str, env: Mapping[str, str]) -> str | None:
    """The environment variable that sets this key, matched in any case as the settings read it."""
    wanted = f"{ENV_PREFIX}{section}{ENV_NESTING}{name}".upper()
    return next((variable for variable in env if variable.upper() == wanted), None)


class NotSettable(ValueError):
    """A path the page may not set: not a listed key, or one an environment variable sets."""


class RefusedValue(ValueError):
    """A value the harness would not keep; the message names the key, never the value."""


MASK = "…"


def check_values(
    settings: Settings, env: Mapping[str, str], values: Mapping[str, str | None]
) -> None:
    """Raises unless each path is a listed key no variable sets, with a value worth keeping."""
    listed = {credential.path: credential for credential in credentials(settings, env)}
    for path, value in values.items():
        credential = listed.get(path)
        if credential is None:
            raise NotSettable(f"{path} is not a credential this page sets")
        if credential.set_by_env is not None:
            raise NotSettable(f"{path} is set by {credential.set_by_env}; change it there")
        if value is None and credential.required:
            raise NotSettable(f"{path} cannot be removed; the harness cannot start without it")
        if value is not None:
            _check_value(settings, path, value)


def _check_value(settings: Settings, path: str, value: str) -> None:
    if not value.strip():
        raise RefusedValue(f"{path}: an empty key is not saved; use Remove instead")
    if MASK in value:
        raise RefusedValue(f"{path}: that is the masked preview, not the key; paste the whole key")
    section_name, name = path.split(".", 1)
    section = getattr(settings, section_name)
    try:
        type(section).model_validate({**section.model_dump(), name: value})
    except ValidationError as err:
        reasons = "; ".join(error["msg"] for error in err.errors())
        raise RefusedValue(f"{path}: {reasons}") from err
