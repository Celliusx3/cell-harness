# 03 The computer sees chat files and skills at their own paths

**Status.** done

**What to build.** `mcp-servers/computer`: `COMPUTER_FILES_DIR` mounted read-write and `COMPUTER_SKILLS_DIRS` (a path list) read-only, each at the same absolute path inside the container; a missing folder fails at startup. A container whose mounts differ from the configured ones is removed and run again (its home volume stays), the way a container missing the gateway port is today. `backend/config.json` sets both.

**Checks.** A unit test with the fake Docker: a container without the files mount is removed and re-run with both `-v` arguments; a matching one is reused.

**Blocked by.** 01
