# 02 The app runs on the PC image: screen, take-control, terminal, files

**Status.** done

**What to build.** The image adds `pc-browser`, which brings Chromium to the
front, or starts it on `:1` with its debugging port on `127.0.0.1:9222` and its
profile under `/home/pc`. It adds `embed.html`, our noVNC page for the live
screen, and `hsetroot`, without which fluxbox shows an error window. The server
moves to the image's names: `HOME` in `models/pc.py` becomes `/home/pc`, the
working folder in `services/gateway.py` becomes `/tmp/pc`, and `OPEN_CHROME`
in `services/machine.py` names `pc-browser`. Tests that pin those values
change with them. `IMAGE` in `config.py` moves to the published digest once
GitHub has built it.

**Checks.** Start the app. The Computer page shows the desktop with Chromium.
Take control and click a link, and the page changes. In the terminal,
`python3 --version` answers. A file saved in the chat's folder shows in the
files list. `make test-mcp-servers` and `make lint-mcp-servers` are green.

**Blocked by.** 01
