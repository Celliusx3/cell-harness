# The full Mac app

`docs/specs/mcp-screen/` replaces this spec's capability decisions: only the PC
is built in, the person adds every other MCP server on a screen, and the app no
longer carries uv or Node.

## Problem

The Mac app has chat, bots and one skill. It has no PC and no capabilities:
no web search, maps, markets, memory or YouTube. To use those you must keep
`make dev` running from the repo. You want one app, for you and for friends,
that has everything.

## What changes for you

1. You run `make app`. It writes one `.dmg` for Apple Silicon Macs.
2. You open the app. The setup window asks for the model key, as today.
3. The chat opens. Capabilities that need no key, such as web search,
   memory, YouTube and jobs, are there at once.
4. You open the Computer page. The first time, the app downloads the PC, and
   then you see its desktop with Chromium.
5. You ask a bot to open a site. It uses the PC's browser, as in `make dev`.
6. You open Credentials and add a "Capability key" for Places with your
   Google Maps key. Places starts within seconds, with no restart.
7. You run `make dev` while the app is open. Each has its own chats, keys
   and PC.
8. A friend installs the same `.dmg`. Places and Markets stay off for them
   until they add their own keys.

## Decisions

1. **One app for everyone.** `make app` builds the full app. The chat-only
   app goes away.
2. **The app carries uv and Node, checked by their published hashes.** It
   already carries Python and Deno this way. Cherry Studio ships uv and bun
   in its app in the same way. Goose instead downloads them on first use,
   and its docs say that fails on restricted networks.
3. **Our own capabilities are installed into the app when it is built.**
   These are the uv projects under `mcp-servers/`. The third-party ones are
   Exa, system monitor, YouTube, memory and jobs. The app's own `npx` and
   `uvx` fetch them on first start, at pinned versions. To decide at
   approval.
4. **The PC runs from inside the app.** microsandbox's `msb` is ad-hoc signed
   with the hypervisor permission, and it runs on this Mac with System
   Integrity Protection on. The app keeps that permission when it signs
   itself. microsandbox signs its own npm package the same way.
5. **The app's PC is its own.** Its microsandbox folder and PC name differ
   from `make dev`'s, so both run at once.
6. **A capability declares the keys it needs, and stays off until they are
   saved.** Claude Desktop's extensions work this way: a required field
   that is empty keeps the extension off.
7. **Capability keys are a credential type.** They are sealed in the keyring
   beside the other credentials. Saving one restarts that capability, as
   saving a Telegram token restarts Telegram today.
8. **Apple Silicon only, ad-hoc signed.** As the app is today.

## Out of scope

- Intel Macs, Windows and Linux.
- Apple signing, notarization and automatic updates.
- Using `make dev`'s chats, keys or PC from the app.
- Choosing which capabilities the app has. It has every one in the config.

## How we will know it works

1. Run `make app`. A `.dmg` appears, and the app passes a strict signature
   check as ad-hoc.
2. Run the packaged app with `PATH=/usr/bin:/bin` and an empty home folder.
   It starts, and "hi" gets an answer.
3. Ask a bot to search the web. It answers from Exa.
4. Open the Computer page. The PC's desktop shows. A bot opens a site in it.
5. Check the PC's folder. It is inside the app's data folder, and
   `make dev`'s PC is untouched.
6. Places is not offered to bots before its key is saved. Save the key on
   Credentials, and a bot finds a place within a minute, with no restart.
7. Run `make dev` while the app is open. Both answer, and neither shows the
   other's chats.
