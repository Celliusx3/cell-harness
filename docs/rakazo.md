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
| `browser_act(ref, …)` | the result of clicking or typing on that ref |
| `computer_observe()` / `computer_act(actions)` | a screenshot — only when a page cannot be read as text |

Three things keep the context small, and phase 19 copies all three:
- An unchanged screen returns its metadata and "the previous screenshot is still valid", not the image.
- Only the latest two screenshots and the latest three page states stay in the request; older ones become a one-line note.
- The live view the person watches is a VNC stream to their browser. It never reaches the model.

## 2. The computer image

`ghcr.io/elie222/rakazo/computer` (Debian, ~2 GB) runs Xvfb, fluxbox, Chromium and
noVNC, and exposes two ways in:

- **`POST :7070/v1/desktop`**, bearer token from `RAKAZO_COMPUTER_CONTROL_TOKEN`:
  `{display, steps: [{argv: [xdotool …]} | {waitMs}], observe, settleMs}` →
  `{completed, observation}` with a PNG. `infra/sandboxes/computer/control.py`.
- **`rakazo-page-browser navigate|snapshot|act`**, a stdlib-only script inside the
  image that drives the live Chromium over CDP. `docker exec` runs it.

Measured: 226 MiB with Chrome closed, 522–627 MiB with a shop page open.

## 3. Feature inventory

| Rakazo | cell-harness today | Where it lands |
|---|---|---|
| A bot browses in its own Chrome | nothing | Phase 17 |
| The live view in the side panel | MCP Apps, and sysmon's poll-through-`tools/call` pattern | Phase 17 |
| Take control, `request_takeover` | client tools (`get_location`) and the approval card | Phase 18 |
| The bot reads screenshots | `Text` and `ToolReference` blocks only; images become placeholder text | Phase 19 |
| Routines and webhook triggers | nothing | Phase 20 |
| Connected apps (Composio, Pipedream, remote MCP) | MCP servers | already there |
| Telegram, Slack and other messaging | Telegram, Discord | already there |
| Memory | Basic Memory server | already there |
| Several bots, delegation | Phase 10 (open), Phase 14 (optional) | existing phases |
| A computer per bot, a shared team computer | nothing | later; needs the conversation on MCP calls |
| Voice, mobile app, teach a routine by watching | nothing | not planned |

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

Android 15's compatibility definition requires 816 MB on a phone; Android Go's 512 MB
applies only to 8.1–10, which Redroid cannot boot on current kernels. Every option
costs more than the desktop's 0.6 GB, so mobile websites go through phase 17's
browser and a phone waits until a bot needs a native app.
