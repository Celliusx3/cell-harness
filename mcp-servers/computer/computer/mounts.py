"""The folders the computer shares with the Mac, read-only or not, and whether it has them."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from computer.config import Config
from computer.docker import DockerError

MOUNTS_FORMAT = "{{json .Mounts}}"


class Mount(BaseModel):
    """One of the container's mounts, in the field names `docker inspect` prints."""

    model_config = ConfigDict(frozen=True)

    type: str = Field(alias="Type")
    source: str = Field(alias="Source")
    destination: str = Field(alias="Destination")
    read_write: bool = Field(alias="RW")


MOUNTS: TypeAdapter[list[Mount]] = TypeAdapter(list[Mount])


def shared_folders(config: Config) -> tuple[Mount, ...]:
    """The chat files read-write and every skill folder read-only, each at its own path."""
    writable = [(config.files_dir, True), *((folder, False) for folder in config.skills_dirs)]
    return tuple(
        Mount(Type="bind", Source=str(folder), Destination=str(folder), RW=read_write)
        for folder, read_write in writable
    )


def volume_arguments(config: Config) -> list[str]:
    """`-v` for each shared folder, a read-only one ending in `:ro`."""
    return [
        arg
        for mount in shared_folders(config)
        for arg in ("-v", f"{mount.source}:{mount.destination}{'' if mount.read_write else ':ro'}")
    ]


def is_mounted_as_configured(inspected: str, config: Config) -> bool:
    """Whether the container's bind mounts, as `docker inspect` prints them, are the shared ones."""
    try:
        mounts = MOUNTS.validate_json(inspected)
    except ValidationError as err:
        raise DockerError(
            "docker inspect answered the computer's mounts with something this server cannot read"
        ) from err
    binds = frozenset(mount for mount in mounts if mount.type == "bind")
    return binds == frozenset(shared_folders(config))
