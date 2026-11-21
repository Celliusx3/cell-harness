"""What the workspace tools tell the model: each tool's description and its arguments'."""

from __future__ import annotations

WORKSPACE_READ = (
    "Read a text file in your workspace, or list a folder. `path` is the absolute path of the "
    "file or folder, inside a workspace folder you were told about. A file's lines come back "
    "numbered from 1. `start_line` and `end_line` pick a range, both included. Leave both out "
    "to read from the first line. At most 2000 lines come back, and the result says where it "
    "stopped. A folder comes back as one entry per line, folders first, each folder's name "
    "ending in /."
)
WORKSPACE_WRITE = (
    "Create a new text file in your workspace. `path` is the file's absolute path, inside a "
    "workspace folder you were told about, and missing folders are made. The call is refused "
    "when the file exists. Change an existing file with `workspace_edit`."
)
WORKSPACE_EDIT = (
    "Change a text file in your workspace by replacing one exact piece of its text. `path` is "
    "the file's absolute path. Read the file with `workspace_read` first: the edit is refused "
    "when you have not read the file, or when it changed since you last read it. `find` must "
    "appear exactly once in the file, spaces and line breaks included. When it appears more "
    "than once, add the text around it until it is unique. `replace` is the new text, and an "
    "empty `replace` deletes `find`."
)
WORKSPACE_SEARCH = (
    "Search every text file in a folder of your workspace, and in the folders inside it, for a "
    "piece of text, ignoring case. `path` is the folder's absolute path; leave it out to search "
    "this chat's workspace. Each match comes back as its file's absolute path, its line number "
    "and the line. At most 100 matches come back, and the result says when there were more."
)

PATH = "An absolute path inside a workspace folder you were told about."
START_LINE = "The first line to read, counting from 1."
END_LINE = "The last line to read, included."
TEXT = "The whole text of the new file."
FIND = "The exact text to replace, which must appear once in the file."
REPLACE = "The text that takes its place."
QUERY = "The text to find, at least one character."
SEARCH_PATH = "The absolute path of the folder to search; leave it out for this chat's workspace."
