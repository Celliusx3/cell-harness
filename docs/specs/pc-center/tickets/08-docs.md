# 08 The docs say the PC is the center

**Status.** open

**What to build.** CLAUDE.md says the PC is a startup requirement, beside Deno,
that it runs in a bundled microVM, and that it reaches only public addresses.
`docs/rules.md` gives the reasons. `PHASES.md` records the reversed decision
"Where the computer runs" and closes the known risk about the Mac's ports, each
with the date. `mcp-servers/README.md` no longer says Docker is required.

**Checks.** `grep -n "host.docker.internal" PHASES.md` shows the risk marked
closed. `grep -n -i microsandbox CLAUDE.md docs/rules.md` finds both.

**Blocked by.** 05, 06
