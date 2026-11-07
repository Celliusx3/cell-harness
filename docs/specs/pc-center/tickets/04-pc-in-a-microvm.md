# 04 The PC runs in a microVM inside the app

**Status.** open

**What to build.** Add the `microsandbox` Python package to
`mcp-servers/computer`, and a `MicrosandboxEngine` beside `DockerEngine`. The
home folder is a named volume. Ports are published on loopback only. A setting
`COMPUTER_ENGINE`, `microsandbox` or `docker`, picks one in
`backend/config.json`, with `microsandbox` set.

**Checks.** With Docker stopped, start the app. The Computer page shows the
desktop, and taking control lets a click change a page. Sign in to a test site,
restart the app, and the sign-in is still there. The engine's unit tests run
against a fake.

**Blocked by.** 03
