# 04 The Mac app has no setup window

**Status:** open

**What to build.**

- `desktop/src/main.ts` no longer asks for a key before the harness starts.
- Before the harness starts, it adds a new encryption key to the settings file when the file holds none.
- `desktop/src/setup.ts` becomes `desktop/src/localSettings.ts`. It keeps the settings file's read, write and encryption key parts.
- The window, its page, its script and its preload go, with their tests and the `src/setup.html` entry in `desktop/package.json`.

**Checks.**

- A node:test: a missing file, and a file with no encryption key, both gain one. Every other value is kept.
- A node:test: an existing encryption key is never replaced, and the file has mode 600.
- `npm test` in `desktop/` passes.
- By hand: `npm start` with `HOME` at a scratch folder opens one window, on the setup screen. A key and Start reach the chat.

**Blocked by.** 03
