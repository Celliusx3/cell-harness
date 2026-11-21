"""Why an upload is not kept, a path is refused, or a workspace file is left as it was."""

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


class WorkspaceFileError(Exception):
    """A workspace tool's call that changed nothing, worded for the model that made it."""


class OutsideWorkspaceError(WorkspaceFileError):
    """A path that is not absolute, or lands outside every workspace the caller was told about."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"{path} is not inside a workspace you were told about; give an absolute path "
            "in one of those folders"
        )


class WorkspaceFileExistsError(WorkspaceFileError):
    """A new file asked for where something is already."""

    def __init__(self, path: str) -> None:
        super().__init__(f"{path} already exists; change it with workspace_edit")


class NotAFileError(WorkspaceFileError):
    """A file asked for where there is none."""

    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is not a file in the workspace")


class NotAFolderError(WorkspaceFileError):
    """A folder asked for where there is none."""

    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is not a folder in the workspace")


class NotTextError(WorkspaceFileError):
    """A file whose bytes are not UTF-8 text."""

    def __init__(self, path: str) -> None:
        super().__init__(f"{path} is not a UTF-8 text file")


class BadRangeError(WorkspaceFileError):
    """A range of lines that picks no line of the file."""


class EmptyFindError(WorkspaceFileError):
    """An edit with nothing to find."""

    def __init__(self) -> None:
        super().__init__("find is empty; give the exact text to replace")


class FindMismatchError(WorkspaceFileError):
    """An edit whose `find` is not in the file exactly once."""

    def __init__(self, count: int) -> None:
        super().__init__(
            f"find appears {count} times in the file, and must appear exactly once; "
            "nothing was changed"
        )


class NotReadError(WorkspaceFileError):
    """An edit of a file the editing model history has not read."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"{path} has not been read yet. Read it with workspace_read before editing it."
        )


class ChangedSinceReadError(WorkspaceFileError):
    """An edit of a file whose text is no longer what the editing model history last read."""

    def __init__(self, path: str) -> None:
        super().__init__(
            f"{path} changed since you last read it. Read it again with workspace_read "
            "before editing it."
        )


class NoWorkspaceError(WorkspaceFileError):
    """A call made where no workspace was told of."""

    def __init__(self) -> None:
        super().__init__("this chat has no workspace")


class WorkspaceFileTooLargeError(WorkspaceFileError):
    """A file, or a new file's text, past the most a workspace tool reads or writes."""

    def __init__(self, path: str, max_bytes: int) -> None:
        super().__init__(
            f"{path} is too large: larger than {max_bytes} bytes, the most a workspace tool "
            "reads or writes"
        )


class WorkspaceDiskError(WorkspaceFileError):
    """A path the disk refused to read, list or change."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path} could not be used on disk ({reason})")
