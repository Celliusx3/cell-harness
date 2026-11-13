# computer

The PC every bot shares: one Linux desktop with Chrome, run by microsandbox or
Docker. What it does is in the `computer` row of
[mcp-servers/README.md](../README.md); this page is where its code is.

```
computer/
  server.py, config.py, clock.py   the composition root and its settings
  models/      the data types, one subject per file
  engine.py    the Engine interface, as secrets/repository/secret_repository.py is
  engines/     docker.py and microsandbox.py, as secrets/repository/disk_secret_repository.py is
  services/    the PC, its shell, browser, files, screen and Mac programs
  startup/     whether this machine can run a PC
  tools/       what the model calls
```

| Folder | Open it for | For example |
|---|---|---|
| `server.py`, `config.py`, `clock.py` | how the server is put together and what it reads from the environment | `config.py` for `COMPUTER_ENGINE` and `COMPUTER_IDLE_MINUTES` |
| `models/` | what a tool takes and returns, and what an engine is handed | `models/pc.py` for `PcSpec`, everything the PC is made with |
| `engine.py` | the calls every engine answers | `Engine.replacement_reason`, why a PC must be made again |
| `engines/` | how one engine runs the PC | `engines/microsandbox.py` for the VM's network rules |
| `services/` | what the PC does for a tool call | `services/machine.py` for the PC's lifecycle and idle stop |
| `startup/` | why the server refuses to start | `startup/readiness.py` for what to turn on |
| `tools/` | what the model and the Computer page call | `tools/browser.py` for `browser_navigate` |

## The PC image

`image/` is the recipe for the PC: a plain Debian with Chromium, Xvfb, fluxbox,
x11vnc, noVNC and xdotool, and our own programs, `pc-start`, `pc-browser`,
`pc-page` (pages through agent-browser) and the noVNC page `embed.html`.
Nothing in it comes from Rakazo.

A push that changes `image/` makes GitHub build it for arm64 and amd64
(`.github/workflows/pc-image.yml`) and publish it as
`ghcr.io/celliusx3/cell-harness/pc:sha-<commit>`. The run's summary prints the
image's digest. To move the app to it, put that digest in `IMAGE` in
`computer/config.py`; a tag can move, and a digest cannot. `COMPUTER_IMAGE`
overrides it for one run.

To try a change without publishing, build it and load it into microsandbox:

```sh
docker buildx build --load -t pc-image:dev image
docker save pc-image:dev -o /tmp/pc-image.tar
msb load -i /tmp/pc-image.tar -t pc-image:dev   # msb is bundled in .venv's microsandbox package
```

then start the app with `COMPUTER_IMAGE=pc-image:dev` in the `computer` server's env.

