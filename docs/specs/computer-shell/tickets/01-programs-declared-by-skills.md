# 01 · Programs declared by skills

**Status.** done

**What to build.** In `mcp-servers/computer/`:
- A skill declares a Mac program in its `SKILL.md` frontmatter `metadata` (a string-to-string map):
  - `host-service` is the command line, split like a shell would, with the placeholders `{port}`, `{token_file}` and `{files}`.
  - `host-service-env` is the prefix, uppercase letters, digits and underscores, under which commands get `<PREFIX>_ADDR` (`host.docker.internal:<port>`) and `<PREFIX>_TOKEN`.
- New `computer/host_services.py` replaces `computer/photocraft.py`. It finds the declarations in the skill folders the computer mounts (`config.skills_dirs`; a missing program or a malformed declaration is logged and skipped), gives each a free loopback port and a new token, and starts each for the server's life, best effort. Each is killed and reaped at shutdown and its token file removed.
- `Shell` takes the commands' variables instead of a PhotoCraft.
- `config.py` loses `COMPUTER_PHOTOCRAFT`, `photocraft` and `missing_photocraft`. `server.py` wires the services.
- `pyproject.toml` gains `pyyaml`, then re-lock.
- Tests: PhotoCraft's tests become host-service tests over a fake program.
- `backend/config.json` drops `COMPUTER_PHOTOCRAFT`. `mcp-servers/README.md` and `.claude/skills/drive-cell-harness/features/computer.md` say what a skill can declare.

**Checks.** The computer suite stays green, with new tests:
- a declared program is started and reaped;
- its variables reach a command;
- a missing or malformed declaration is skipped with a log line;
- a skill outside the mounted folders is never read.

`grep -rni photocraft mcp-servers/computer/computer backend/config.json` finds nothing.

**Blocked by.** none
