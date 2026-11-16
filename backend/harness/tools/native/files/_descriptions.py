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

ASK_ABOUT_IMAGES = (
    "Asks the bot's own model one question about images in this chat's files, with no "
    "conversation history: only the instructions and the images are sent, and it costs one "
    "model call. For many sets of images, list the calls in a file for ask_about_image_jobs. "
    "Returns {answer, saved_to}: answer is the reply parsed as JSON when it is JSON, a ```json "
    "fence around it removed, else the reply's text; saved_to is the path the reply was "
    "written to, or null when save_to was not given."
)
ASK_PATHS = "Absolute paths of 1 to 12 JPEG or PNG images, each a file in this chat's folder."
ASK_INSTRUCTIONS = (
    "Everything the model is told: what to look for in the images and the exact shape of the "
    "answer, such as the JSON to return. It sees nothing else."
)
ASK_SAVE_TO = (
    "Absolute path of a file inside this chat's folder to write the reply to, replacing it if it "
    "exists; leave it out to only return the reply."
)

ASK_ABOUT_IMAGE_JOBS = (
    "Makes every ask_about_images call a jobs file lists, one after another, each with no "
    "conversation history and saved to its own file. The file is a JSON list of jobs, each an "
    'object with "paths", "instructions" and "save_to", as ask_about_images takes them. Returns '
    "{answered, failed}: how many replies were saved, and each job that was not, by its save_to, "
    "with why."
)
JOBS_PATH = "Absolute path of the jobs file, inside this chat's files."
