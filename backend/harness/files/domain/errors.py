"""Why an upload is not kept, or a workspace path is refused."""

from __future__ import annotations


class FileTooLargeError(Exception):
    """An upload went past the limit, and nothing of it was kept."""

    def __init__(self, name: str, max_bytes: int) -> None:
        super().__init__(
            f"{name!r} is larger than {max_bytes} bytes, the most one upload may be; "
            "nothing was saved"
        )


class UnsafeFileNameError(ValueError):
    """A file name with nothing left to save under once its folders are stripped."""


class WorkspacePathError(LookupError):
    """A workspace path that leaves the workspace, is missing, or is not a folder."""
