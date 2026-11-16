# 03 The PC's file tools resolve relative paths in the workspace

**Status.** open

**What to build.** Build this only if Decision 7 is approved. In `mcp-servers/computer`, the file tools resolve a relative path against the workspace in the call's `_meta`, as the shell does since ticket 01. They use `/home/pc` when there is none. The change is in `models/files.py` and the file tools that build a path from it.

**Checks.** A computer server test writes `notes.txt` with a workspace `_meta`. The file lands in the workspace. With no `_meta`, it lands in `/home/pc`. An absolute path is unchanged in both cases. `make test-mcp-servers` passes at 80%.

**Blocked by.** 01
