# Cell Harness as a Mac app

## Problem

A friend cannot use cell-harness without the repo. Today they must clone it, install uv, Node and Deno, write a settings file with two keys, and keep `make dev` running in a terminal. The chat is a browser tab, and it stops when the terminal closes.

## What changes for you

1. You run `make app`. It writes one `.dmg` file for Apple Silicon Macs.
2. You upload the file to a GitHub release and send a friend the link.
3. The friend drags Cell Harness into Applications and opens it.
4. macOS says Apple could not verify it. The friend clicks Open Anyway in Privacy & Security, once.
5. A setup window asks for an API key. The endpoint and the model are filled in.
6. The friend pastes their own key and clicks Start.
7. The chat opens in its own window, with chat, bots and skills. No capability is connected.
8. The friend closes the window. An icon stays in the menu bar, and the harness keeps running.
9. The menu has Open, Open in Browser, Show Settings File and Quit.
10. Quit stops the harness and the page server.
11. On your own Mac, the app and `make dev` run at the same time, with separate chats.

## Decisions

- The shell is Electron, showing the same web pages. Rakazo, OpenMausBot and Hermes Agent ship this way.
- The pages stay a Next server, run on Electron's own Node. OpenMausBot runs its server the same way. Next's static export cannot serve the chat's dynamic pages or forward the API.
- The app carries a pinned Python with the harness's packages, and Deno. Hermes Agent ships a pinned Python the same way.
- The app has an ad-hoc signature, not an Apple one. electron-builder makes one when the identity is `-`. None of the five projects studied ships unsigned.
- The first-start window saves one owner-only settings file. Rakazo's setup window saves its choice the same way.
- The harness listens on port 4886 and the pages on port 4887, both on this Mac only. Voicebox fixes its port the same way.
- A menu-bar icon keeps the app alive. OpenClaw is a menu-bar app.
- Quit stops both programs, and the next start stops a copy a crash left behind. OpenClaw and Voicebox stop their servers on quit.
- The sidebar hides the Computer link when no computer is set up.
- All data lives in `~/Library/Application Support/Cell Harness/`, apart from `make dev`'s `~/.harness`.

## Out of scope

- Every MCP capability, and every shipped skill except create-skill.
- The computer. The later pick for a missing Docker is Rakazo's: explain and link, install nothing.
- A Settings page for keys. Telegram and Discord tokens go in the settings file.
- Notifications, start at login, a Dock badge and a global shortcut.
- Intel Macs, Windows and Linux.
- Apple signing, notarization and automatic updates.

## How we will know it works

- Run `make app`. A `.dmg` appears, and its app passes a strict signature check as ad-hoc.
- Open the app with no settings file. The setup window appears. Paste a key and click Start. The chat opens and answers "hi".
- Run the packaged app with a PATH that has no uv, Node or Deno. It still starts and answers.
- Close the window. The menu-bar icon stays, and `127.0.0.1:4887` still answers in a browser.
- Click Quit. Nothing listens on ports 4886 or 4887 afterwards.
- Kill the app hard, then open it again. It stops the old harness and starts.
- Run `make dev` while the app is open. Both answer, and neither shows the other's chats.
- From another machine on the same network, the app's ports do not answer.
- Remove the API key from the settings file. The setup window appears again.
