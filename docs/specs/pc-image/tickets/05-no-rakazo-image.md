# 05 Nothing of Rakazo's image is left, and the docs say so

**Status.** done

**What to build.** Rename every remaining `RAKAZO_` variable and `rakazo-`
program name that the server passes to the PC. `mcp-servers/computer/NOTICE`
lists only the server's own adapted parts (spec decision 10). `docs/rakazo.md`
section 2 says the PC no longer runs this image. The computer server's README
says how the image is built and how to move the config to a new version.
PHASES.md's status names the PC image.

**Checks.** `grep -ri rakazo mcp-servers/computer/image mcp-servers/computer/computer/config.py backend/config.json`
finds nothing. `make lint`, `make test`, `make lint-mcp-servers` and
`make test-mcp-servers` are green.

**Blocked by.** 03, 04
