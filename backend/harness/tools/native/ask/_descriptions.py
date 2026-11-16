"""What the ask tools tell the model: each tool's description and its arguments'."""

from __future__ import annotations

ASK_MODEL = (
    "Asks the bot's own model one question, with no conversation history: only the "
    "instructions and the files in paths are sent, and it costs one model call. A PNG or JPEG "
    "is sent as an image, which needs a model that can see; any other file is sent as its "
    "UTF-8 text. For many questions, list the calls in a file for ask_model_jobs. Returns "
    "{answer, saved_to, usage}: answer is the reply parsed as JSON when it is JSON, a ```json "
    "fence around it removed, else the reply's text; saved_to is the path the reply was "
    "written to, or null when save_to was not given; usage is the call's tokens, or null when "
    "the provider did not report them."
)
ASK_PATHS = (
    "Absolute paths of up to 12 files in this chat's folder: PNG or JPEG images, or UTF-8 "
    "text files of at most 200 KB. Leave it out to send only the instructions."
)
ASK_INSTRUCTIONS = (
    "Everything the model is told: what to do with the files and the exact shape of the "
    "answer, such as the JSON to return. It sees nothing else."
)
ASK_SAVE_TO = (
    "Absolute path of a file inside this chat's folder to write the reply to, replacing it if it "
    "exists; leave it out to only return the reply."
)

ASK_MODEL_JOBS = (
    "Makes every ask_model call a jobs file lists, a few at a time, each with no conversation "
    "history and saved to its own file. The file is a JSON list of jobs, each an object with "
    '"paths", "instructions" and "save_to", as ask_model takes them. Returns '
    "{answered, failed, usage}: how many replies were saved, each job that was not, by its "
    "save_to, with why, and the tokens of every call together."
)
JOBS_PATH = "Absolute path of the jobs file, inside this chat's files."
