"""Files: what the person attaches and what a tool hands back, kept in each chat's workspace."""

from harness.files.domain.errors import (
    ChangedSinceReadError,
    FileTooLargeError,
    FindMismatchError,
    UnsafeFileNameError,
    WorkspaceFileError,
    WorkspacePathError,
)
from harness.files.domain.models import (
    ChatFile,
    FileText,
    FolderEntries,
    WorkspaceEntry,
    WorkspaceListing,
)
from harness.files.domain.search import Match
from harness.files.domain.text_edit import TextEdit, version_of
from harness.files.repository.disk_file_repository import DiskChatFileRepository
from harness.files.repository.file_repository import ChatFileRepository
from harness.files.repository.workspace_text_repository import WorkspaceTextRepository
from harness.files.service.file_service import ChatFileService
from harness.files.service.workspace_text_service import WorkspaceTextService

__all__ = [
    "ChangedSinceReadError",
    "ChatFile",
    "ChatFileRepository",
    "ChatFileService",
    "DiskChatFileRepository",
    "FileText",
    "FileTooLargeError",
    "FindMismatchError",
    "FolderEntries",
    "Match",
    "TextEdit",
    "UnsafeFileNameError",
    "WorkspaceEntry",
    "WorkspaceFileError",
    "WorkspaceListing",
    "WorkspacePathError",
    "WorkspaceTextRepository",
    "WorkspaceTextService",
    "version_of",
]
