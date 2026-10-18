# 05 Scripts in the computer reach PhotoCraft

**Status.** done. Reshaped by `docs/specs/computer-shell/`: this skill now declares the command in its `SKILL.md` metadata, and the computer starts any program a mounted skill declares, naming none itself. The lock is the skill's own, in `$HOME`.

**What to build.** `mcp-servers/computer`: when `COMPUTER_PHOTOCRAFT` names the binary, the server starts `photocraft-cli serve --port <free> --control-token-file <file> --automation-read-root <files dir> --automation-write-root <files dir>` on the Mac, and kills it in `finally`. Each shell command gets `PHOTOCRAFT_ADDR=host.docker.internal:<port>` and `PHOTOCRAFT_TOKEN` through `docker exec -e`. The token file lives outside the mounts.

**Checks.** Unit tests: the child is started with the roots and a token file and is gone after the server stops; every `exec` carries both variables.

**Blocked by.** 04
