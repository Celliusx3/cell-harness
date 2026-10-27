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
