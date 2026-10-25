# 03 First-start setup

**Status:** open

**What to build.**

- `desktop/src/setup.ts` decides whether setup is needed: the local settings file is missing, or `llm.api_key` is empty.
- It merges a new key into the file and keeps every other value, such as a Telegram token.
- It adds a random 32-byte hex `secrets.encryption_key` only when none exists.
- It writes the file atomically with mode 600.
- A file that is not valid JSON stops the app with a dialog naming the file. It is never overwritten.
- `desktop/src/setup.html`, `setup.js` and a preload show the form. The endpoint and model from `desktop/config.json` are filled in.
- An endpoint or model that differs from those values is saved in the local file.

**Checks.**

- node:test on `setup.ts`: a missing file and an empty key both need setup.
- A saved key keeps the other fields, and an existing encryption key is never replaced.
- Bad JSON raises, and the written file has mode 600.
- By hand: delete the local file and run `npm start`. Paste a key and click Start. The chat opens and answers.

**Blocked by.** 02
