# 02 One engine interface for the PC

**Status.** open

**What to build.** Reshaping, with no change in behaviour. In
`mcp-servers/computer`, replace the raw `docker` argument lists behind
`Docker.run` with a typed `Engine` protocol in `engine.py`. It has create,
start, stop, remove, state, exec and published port. `DockerEngine` implements
it. This ticket moves `machine.py` and `desktop.py` to it.

**Checks.** `make test-mcp-servers` passes before and after, with the same
count. The PC still starts in Docker and the Computer page shows it.

**Blocked by.** none
