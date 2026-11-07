# 01 The data types move into models/

**Status.** done

**What to build.** Create `computer/models/`. Split `models.py` into `page.py`
(Action, Opened, Page, Acted), `files.py` (HomePath, FileEntry, Listing,
FileText, FileBytes, Uploaded), `screen.py` (ScreenSession, ScreenMode) and
`shell.py` (CommandRun, CommandStatus). Split `command.py` into
`models/command.py` (CommandResult) and `models/errors.py` (EngineError,
EngineTimeout). Move PcSpec, SharedFolder, HomeVolume, Program and PcState
from `engine.py` into `pc.py`. Update every import, and delete the old files.

**Checks.** `uv run pytest -q` in `mcp-servers/computer` passes 568, before
and after. Breaking one field in each model file makes a test fail.

**Blocked by.** none
