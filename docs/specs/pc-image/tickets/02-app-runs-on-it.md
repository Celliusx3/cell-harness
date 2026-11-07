# 02 The app runs on the PC image: screen, take-control, terminal, files

**Status.** open

**What to build.** The image adds `pc-browser`, which starts Chromium on `:1`
with its debugging port on `127.0.0.1:9222` and its profile under `/home/pc`,
and `pc-focus-or-launch`, which brings a running program to the front or
starts it. The server moves to the image's names: `IMAGE` in `config.py`
becomes the digest from 01, `HOME` in `models/pc.py` becomes `/home/pc`, the
working folder in `services/gateway.py` becomes `/tmp/pc`, and `OPEN_CHROME`
in `services/machine.py` names `pc-focus-or-launch pc-browser`. Tests that pin
those values change with them.

**Checks.** Start the app. The Computer page shows the desktop with Chromium.
Take control and click a link, and the page changes. In the terminal,
`python3 --version` answers. A file saved in the chat's folder shows in the
files list. `make test-mcp-servers` and `make lint-mcp-servers` are green.

**Blocked by.** 01
