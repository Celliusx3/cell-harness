# 06 The model sees an image file, and a skill says where it lives

**Status.** done. Narrowed by the skill-scripts change: only a skill shipped with the app names its folder; a bot reads the scripts of a skill it can change by `path`, since that folder is not in the computer.

**What to build.** `backend/harness/tools/native/`: `view_image(path)` returns a file under the files root as an image (JPEG or PNG, at most 5 MiB), offered only when `llm.vision` is on, never from scripts. `backend/harness/skills/prompt.py`: the expansion names the skill's absolute folder. `skills/tool.py`: "Any other script cannot run" says instead that a script of another language runs where a tool for commands is offered; a `docs/prompt-failures.md` row.

**Checks.** Unit tests: a path outside the files root fails as an error result; a PNG comes back as an image block; without vision the tool is not offered; the skill text holds its folder.

**Blocked by.** 01
