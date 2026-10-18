# 02 · The file tool package laid out like its siblings

**Status.** done

**What to build.** In `backend/harness/tools/native/files/`:
- `tools.py` holds the four tool definitions (`send_file_tool`, `extract_archive_tool`, `make_archive_tool`, `view_image_tool`) and their name constants.
- `models.py` holds the four argument models.
- `archive.py` and `image.py` keep only the archive and image logic.
- `tool.py` and `archive_tools.py` are deleted. `__init__.py` exports the same names as today.

**Checks.** The whole suite stays green with no test changes beyond imports. `grep -rn "native.files.tool\b\|archive_tools" backend` finds nothing.

**Blocked by.** 01
