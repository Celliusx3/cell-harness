# 03 The logic moves into services/

**Status.** open

**What to build.** Move `machine.py`, `shell.py`, `jobs.py`, `browser.py`,
`files.py`, `desktop.py`, `live_screen.py`, `gateway.py`, `host_services.py`
and `skill_declarations.py` into `computer/services/`, keeping their file
names. Update every import.

**Checks.** The suite passes 568. Breaking one line in each moved service
makes a test fail.

**Blocked by.** 02
