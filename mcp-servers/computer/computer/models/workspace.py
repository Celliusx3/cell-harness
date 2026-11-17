"""The workspace a call names in its `_meta`, and the folder a command starts in."""

from __future__ import annotations

from collections.abc import Mapping

from computer.models.pc import HOME

WORKSPACE_META = "harness/workspace"


def start_folder(cwd: str | None, meta: Mapping[str, object] | None) -> str:
    """`cwd` when given, else the absolute workspace the call's `_meta` names, else HOME."""
    if cwd is not None:
        return cwd
    workspace = (meta or {}).get(WORKSPACE_META)
    return workspace if isinstance(workspace, str) and workspace.startswith("/") else HOME
