# 02 Window on the checkout

**Status:** open

**What to build.**

- A new `desktop/` Electron app: `package.json`, `tsconfig.json`, `src/main.ts`, `src/paths.ts` and `src/processes.ts`.
- Run from this checkout, it starts the harness with `uv run` on 127.0.0.1:4886.
- It starts the page server on Electron's own Node on 127.0.0.1:4887.
- It waits for both ports, then opens one window on `http://127.0.0.1:4887`. Quit stops both children.
- `frontend/next.config.ts` gains `output: "standalone"`.
- `desktop/scripts/build-pages.sh` builds the pages in `desktop/build/` with `BACKEND_PORT=4886`, never in `frontend/.next`.
- Links that leave the app's origin open in the default browser.
- The harness's output goes to a log file in the data folder. If it exits before its port answers, a dialog shows the end of that log.

**Checks.**

- `cd desktop && npm test` runs node:test on `paths.ts` and `processes.ts`.
- The tests cover the spawn spec for each child, both bound to 127.0.0.1, with the two settings variables.
- A test asserts every data path in `desktop/config.json` sits under the folder Electron uses.
- By hand: `npm start` opens the window, and "hi" gets a reply. After Quit, nothing listens on 4886 or 4887.
- By hand: try a bot's "where am I" card in the window, and record what it does.

**Blocked by.** 01
