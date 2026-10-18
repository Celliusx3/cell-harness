"""What the file tools tell the model: each tool's description and its arguments'."""

from __future__ import annotations

SEND_FILE = (
    "Hand the person files from this chat's folder, such as a page a tool saved next to a "
    "file they attached. Each file appears under this call: a picture as a thumbnail they "
    "can open full size, anything else as a download. Returns the paths handed over, and "
    "each path that was not, because it is not a file in this chat's folder."
)
PATHS = "Absolute paths of the files to hand over, each a file inside this chat's folder."

EXTRACT_ARCHIVE = (
    "Unpack a .zip or .cbz the person attached into a new folder beside it, so each file "
    "inside can be opened on its own. Returns the paths of the files it wrote, in the "
    "archive's own order, numbered so that 2 comes before 10."
)
ARCHIVE_PATH = "Absolute path of the .zip or .cbz, a file in the chat files folder."
MAKE_ARCHIVE = (
    "Pack files into one new .cbz or .zip beside the first of them, in the order given, such "
    "as the translated pages of a chapter. Returns the path of the archive it wrote; hand it "
    "to the person with send_file."
)
ARCHIVE_PATHS = "Absolute paths of the files to pack, in order, each in the chat files folder."
ARCHIVE_NAME = "File name of the archive to write, ending in .cbz or .zip, with no folder in it."

VIEW_IMAGE = (
    "Shows you an image file kept with this chat, such as a page a skill's script saved: "
    "a JPEG or PNG of at most 5 MB, by its absolute path."
)
IMAGE_PATH = "The image's absolute path, inside this chat's files."
