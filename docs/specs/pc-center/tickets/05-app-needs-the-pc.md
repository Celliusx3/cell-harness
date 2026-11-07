# 05 The app needs the PC to start

**Status.** open

**What to build.** Add `required: bool = False` to `McpServer` in
`config/sections.py`, and set it on `computer`. At startup, a required server
that fails to connect stops the app. The message names the server and its
error. The `computer` server's error says what to turn on: virtualization on
Mac and Linux, or the Windows Hypervisor Platform.

**Checks.** A unit test starts the MCP service with a required server whose
command fails. Startup raises an error that names the server. A server that is
not required still fails quietly, as today.

**Blocked by.** 04
