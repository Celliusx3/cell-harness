# 07 The skill's PhotoCraft client

**Status.** done

**What to build.** `.agents/skills/translate-comic/scripts/comic/`: a client for PhotoCraft's headless server over TCP. It reads `PHOTOCRAFT_ADDR` and `PHOTOCRAFT_TOKEN`, sends `auth` first, then `doc.open`, `batch` (steps named `command`), `doc.save` and `doc.close`, and raises on `ok: false`. A lock file in `/home/rakazo` (an exclusive `flock`) is held from a page's open to its close. The skill gets its own uv project, tests under `scripts/comic/tests/`, and `make test-skills` with lint and the length check.

**Checks.** Unit tests against a fake JSON-lines server: the first line is `auth`, a batch step carries `command`, an error reply raises, and a second holder of the lock waits.

**Blocked by.** 01
