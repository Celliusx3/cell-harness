# 03 Every PC call goes through the engine

**Status.** open

**What to build.** Reshaping, with no change in behaviour. Move `shell.py`,
`browser.py`, `files.py`, `live_screen.py` and `host_services.py` to the
`Engine` protocol. Delete `Docker.run` and its raw argument lists.

**Checks.** `make test-mcp-servers` passes with the same count.
`grep -rn '"exec"' mcp-servers/computer/computer` finds only `engine.py`.

**Blocked by.** 02
