# Rakazo — teardown, and what the computer track takes from it

[Rakazo](https://github.com/elie222/rakazo) (Apache-2.0) is an open-source copy of
xAI's Grok Bot: always-on bots you message like teammates, each with its own Linux
desktop and Chrome, a live view of that desktop, and a "take control" button. It is a
TypeScript monorepo (Hono API, Graphile worker, Postgres, React, the Pi agent runtime),
and its bots' computers are Docker containers run by a supervisor service.

We cloned it, ran it from its published images and drove it in a browser on
2026-10-03. Everything below that carries a number was measured on that run (M3 Max,
Docker Desktop); everything else is read from its code at commit `df708491`.

## 1. How a bot uses the web

The model never streams a screen. It sees the page only when it calls a tool, and for
a web page it reads text first:

| Tool | What the model gets back |
|---|---|
| `browser_navigate(url)` | the page title |
| `browser_snapshot()` | page text and up to 80 interactive elements, each with a ref |
| `browser_act(actions)` | the result of up to 24 clicks, fills or typing, each on a ref |
| `computer_observe()` / `computer_act(actions)` | a screenshot — only when a page cannot be read as text |

Three things keep the context small. Phase 17 copies the page-state limit and the
view; phase 19 copies the two about screenshots:
- An unchanged screen returns its metadata and "the previous screenshot is still valid", not the image.
- Only the latest two screenshots and the latest three page states stay in the request; older ones become a one-line note.
- The live view the person watches is a VNC stream to their browser. It never reaches the model.

## 2. The computer image

The PC no longer runs this image. Ours is built from scratch in
`mcp-servers/computer/image/` (`docs/specs/pc-image/`); this section is kept as the
teardown of Rakazo's.

`ghcr.io/elie222/rakazo/computer` (Debian, ~2 GB) runs Xvfb, fluxbox, Chromium and
noVNC, and exposes two ways in:

- **`POST :7070/v1/desktop`**, bearer token from `RAKAZO_COMPUTER_CONTROL_TOKEN`:
  `{display, steps: [{argv: [xdotool …]} | {waitMs}], observe, settleMs}` →
  `{completed, observation}` with a PNG. `infra/sandboxes/computer/control.py`.
- **`rakazo-page-browser navigate|snapshot|act`**, a stdlib-only script inside the
  image that drives the live Chromium over CDP. `docker exec` runs it.

Measured: 226 MiB with Chrome closed, 522–627 MiB with a shop page open.

## 3. Feature inventory

The full list, sorted, was the old phase plan's build order
(`git show db9b326:PHASES.md`), and each open row is now a GitHub issue;
"Where it lands" names its row.

| Rakazo | cell-harness today | Where it lands |
|---|---|---|
| A bot browses in its own Chrome | nothing | 12, phase 17 |
| The live view in the side panel | MCP Apps, and sysmon's poll-through-`tools/call` pattern | 12, phase 17 |
| Take control, `request_takeover` | client tools (`get_location`) and the approval card | 13, phase 18 |
| The bot reads screenshots | `Text` and `ToolReference` blocks only; images become placeholder text | 18, phase 19 |
| Routines | nothing | 3, phase 20 |
| Webhook triggers | nothing | 17 |
| Remote MCP servers by URL | local MCP servers only | 5 |
| Composio, Pipedream | MCP servers | not planned |
| Telegram, Slack and other messaging | Telegram, Discord | already there |
| Memory | Basic Memory server | already there |
| Helpers inside a turn, several bots | Phase 10 (open), Phase 14 (optional) | 4 and 16 |
| A computer per bot, a shared team computer | nothing | later; needs the conversation on MCP calls |
| Teach a routine by watching | nothing | 15 |
| Voice, mobile app | nothing | not planned |

## 4. What broke when we ran it

1. **Clicks failed until someone opened the viewer.** The supervisor joins a computer's
   private Docker network only while handing out a screen URL, so every screenshot took
   ~11 s and every click returned 500 until the panel was opened. Phase 17's server
   reaches its container through ports published on `127.0.0.1` instead.
2. **Shops answer bots with a check.** Shopee showed a traffic check, then a slider
   captcha once the bot's clicks worked. Phase 18 exists for this.
3. **Lima's Docker template is rootless**, and rootless `--privileged` is not enough
   for an Android container. Not our problem until a phone is wanted — see §5.

## 5. A phone per bot — measured, and declined

We built a phone service (one Android emulator per bot) and Rakazo phone tools, ran
them end to end, then measured the lighter options:

| Runtime | Memory per phone | Note |
|---|---|---|
| Android emulator, Android 16 Play image, fresh boot | 2.2 GB | the image refuses less than 2 GB of guest RAM |
| The same, resumed from its snapshot | 3.0–3.2 GB | |
| Redroid 15 in a Lima VM, idle / with a page open | 0.8 / 1.25 GB | the VM costs the Mac its whole limit once touched |
| A slimmed Redroid 13 ([kindling](https://github.com/juan52878911/kindling)) | 803 MiB | one source; the floor is ~345 MiB of system processes |
| Redroid 13 in a microsandbox microVM, idle / with an app open | 0.76 / 0.89 GiB | measured in the guest, 2026-11-11; the Mac holds 0.44–1.28 GiB as macOS reclaims pages ([experiment](./specs/android-phone/experiment.md)) |

Android 15's compatibility definition requires 816 MB on a phone; Android Go's 512 MB
applies only to 8.1–10, which Redroid cannot boot on current kernels. Every option
costs more than the desktop's 0.6 GB, so mobile websites go through phase 17's
browser and a phone waits until a bot needs a native app.

**Revisited 2026-11-11 (#65).** Selling native-app use reopened it. Redroid 13
in a microsandbox microVM, on a libkrunfw rebuilt with binder, measured 0.76 GiB
idle and 0.89 GiB with an app open (the row above). One phone every bot shares
fits on an 8 GB Mac beside the desktop, so that is built; a phone per bot is
still no. [docs/specs/android-phone/](./specs/android-phone/spec.md) has the
spec and the experiment.
