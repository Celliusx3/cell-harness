"""The harness's own keys, read from its settings and shown only by their last four characters."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, JsonValue
from pydantic.fields import FieldInfo

from harness.config.sections import READ_ONLY_MARKER, REQUIRED_MARKER, SECRET_MARKER
from harness.config.settings import Settings

SHOWN_CHARACTERS = 4
MIN_MASKABLE_LENGTH = 8


class Credential(BaseModel):
    """One key the harness holds, as a page may see it: whether it is set, never its value."""

    model_config = ConfigDict(frozen=True)

    path: str
    description: str
    is_set: bool
    is_required: bool
    last_four: str | None
    env_variable: str | None


def credentials(settings: Settings, env: Mapping[str, str]) -> tuple[Credential, ...]:
    """Every secret a person sets, in the settings' own order."""
    return tuple(
        _credential(f"{section_name}.{name}", str(getattr(section, name)), field, env)
        for section_name, section in settings
        if isinstance(section, BaseModel)
        for name, field in type(section).model_fields.items()
        if _is_settable_secret(field)
    )


def _is_settable_secret(field: FieldInfo) -> bool:
    extra = _markers(field)
    return bool(extra.get(SECRET_MARKER)) and not extra.get(READ_ONLY_MARKER)


def _markers(field: FieldInfo) -> dict[str, JsonValue]:
    return dict(field.json_schema_extra) if isinstance(field.json_schema_extra, dict) else {}


def _credential(path: str, value: str, field: FieldInfo, env: Mapping[str, str]) -> Credential:
    is_set = value.strip() != ""
    is_maskable = is_set and len(value) >= MIN_MASKABLE_LENGTH
    return Credential(
        path=path,
        description=field.description or "",
        is_set=is_set,
        is_required=bool(_markers(field).get(REQUIRED_MARKER)),
        last_four=value[-SHOWN_CHARACTERS:] if is_maskable else None,
        env_variable=_variable_that_sets(path, env),
    )


def _variable_that_sets(path: str, env: Mapping[str, str]) -> str | None:
    """The environment variable that sets this key, named as the settings name it."""
    config = Settings.model_config
    section, name = path.split(".", 1)
    wanted = f"{config['env_prefix']}{section}{config['env_nested_delimiter']}{name}".upper()
    return next((variable for variable in env if variable.upper() == wanted), None)


class UnsettablePath(ValueError):
    """A path the page may not set."""


class RefusedValue(ValueError):
    """A value the harness would not keep."""


PREVIEW_ELLIPSIS = "…"


def check_values(
    settings: Settings, env: Mapping[str, str], values: Mapping[str, str | None]
) -> None:
    """Raises UnsettablePath or RefusedValue for the first value the page may not save."""
    listed = {credential.path: credential for credential in credentials(settings, env)}
    for path, value in values.items():
        credential = listed.get(path)
        if credential is None:
            raise UnsettablePath(f"{path} is not a credential this page sets")
        if credential.env_variable is not None:
            raise UnsettablePath(f"{path} is set by {credential.env_variable}; change it there")
        if value is None and credential.is_required:
            raise UnsettablePath(f"{path} cannot be removed; the harness cannot start without it")
        if value is not None:
            _check_value(path, value)


def _check_value(path: str, value: str) -> None:
    if not value.strip():
        raise RefusedValue(f"{path}: an empty key is not saved; use Remove instead")
    if PREVIEW_ELLIPSIS in value:
        raise RefusedValue(f"{path}: that is the masked preview, not the key; paste the whole key")
