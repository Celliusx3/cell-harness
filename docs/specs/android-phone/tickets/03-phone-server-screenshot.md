# 03 A bot takes a screenshot of the phone, which starts on first use

**Status.** open

**What to build.** `mcp-servers/phone/`, a uv project laid out like
`mcp-servers/computer/`: `engine.py`, `engines/microsandbox.py`, `models/`,
`services/machine.py` and `tools/`, with its own tests and 80% gate. It sets
`MSB_LIBKRUNFW_PATH` before microsandbox loads. Its one tool, `screenshot`,
creates or starts the phone's microVM on first use, waits for
`sys.boot_completed`, and returns the screen as an image. A `phone` entry goes
in `backend/config.json`.

**Checks.** An integration test against a fake engine: the first `screenshot`
starts the phone once, and a second does not. By hand, in the chat, ask a bot
for a screenshot of the phone. The reply shows the home screen.

**Blocked by.** 02
