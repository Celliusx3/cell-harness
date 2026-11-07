# 04 Bots read and click pages through our page script

**Status.** done

**What to build.** The image installs agent-browser at a pinned version, each
machine type checked by its sha256. `image/pc_page.py`, installed as `pc-page`, is our own Python script
with three commands, `navigate`, `snapshot` and `act`. Each takes its JSON
arguments on stdin and attaches agent-browser to the Chromium on port 9222. It
answers today's shape, `{ok, url, title, tree, completed}`, or `{ok: false,
error}`. A stale reference, or Chromium not up, is an `error` the server
already reads. `services/browser.py` names `pc-page`. Unit tests run the
script against a fake agent-browser.

**Checks.** The unit tests cover each command, a stale reference and Chromium
down, at 80% or more. Start the app and ask a bot "open coingecko.com and tell
me the top coin". It answers from the page. Ask it to open that coin, and it
clicks by reference.

**Blocked by.** 02
