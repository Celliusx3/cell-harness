# cell-harness

Design work for an agent harness of our own, derived from two studied sources.

| Document | What's in it |
|---|---|
| [DESIGN.md](./DESIGN.md) | **The proposal.** What we take from each source, module layout, core contracts, and the open decisions. |
| [PHASES.md](./PHASES.md) | **The execution plan.** What is done, the build order, and each open phase — deliverables, contracts, and acceptance criteria. |
| [docs/deepseek-harness.md](./docs/deepseek-harness.md) | Teardown of `deepseek-ai/deepseek-harness` (256k lines, 227 packages) and three replication tiers. |
| [docs/cell-bot.md](./docs/cell-bot.md) | Teardown of cell-bot (6.9k lines Python), its feature inventory, and its honest gaps. |
| [docs/without-cordis.md](./docs/without-cordis.md) | How to get dsh's plugin properties — reversible registration, per-agent scoping, waterfall events — in ~250 lines of Python, and what we give up. |
| [docs/rules.md](./docs/rules.md) | The reasoning behind every rule and invariant in [CLAUDE.md](./CLAUDE.md). |
| [docs/coding-principles.md](./docs/coding-principles.md) | Behavioral guidelines (Karpathy): think first, KISS/YAGNI, surgical changes, goal-driven. |
| [docs/mcp-tool-scaling.md](./docs/mcp-tool-scaling.md) | Why MCP schemas load on demand, how code mode works and who else ships it, and what the evidence actually says. |
| [docs/skills.md](./docs/skills.md) | The Agent Skills spec, how six clients implement it, and which of their choices bind phase 8. |
| [docs/mcp-apps.md](./docs/mcp-apps.md) | MCP Apps: the contract, what the SDKs ship, how VS Code / Vercel / MCPJam host it, and the choices made here. |

The thesis in one line: **dsh's spine at cell-bot's size** — the event-sourced
log, turn/step semantics, and capability seams from DeepSeek Harness, built with
cell-bot's shallow contracts and typed decisions, targeting ~10k lines of Python.

Shape: a **chat product** (browser UI, conversations, agent catalog,
capabilities via MCP), not a terminal coding harness. That decision drives the
phase ordering.

## Getting started

```sh
cp backend/config.local.example.json backend/config.local.json
# set secrets.encryption_key (`openssl rand -hex 32`), which seals the keyring;
# put your API key in llm.api_key, or delete it and paste the key on the chat's setup screen;
# on start the API key and any bot tokens move into the keyring (see Credentials)
# everything else — model, endpoint, sessions root, MCP servers — is in
# backend/config.json (committed); a server's `env` secrets go in config.local.json
make install                           # uv sync the backend package + dev deps
make test                              # pytest, 80% coverage gate — needs Deno on PATH, https://deno.com
make lint                              # ruff check + format check
```

Deno is a startup requirement: the model reaches every capability by writing a
TypeScript program that runs in a Deno sandbox. The `sysmon` MCP App also needs
Node (`npx`).

Then:

```sh
make dev            # backend :4896 + frontend :4897 together (Ctrl-C stops both)
make dev-backend    # or just one of them
make dev-web
```

Open <http://localhost:4897>.

There is no command-line interface. `harness run` / `list` / `resume` existed to
demo the harness before there was a UI; the API does all three, so keeping them
would be a second surface to hold in step with the first. To smoke-test a
provider without the browser:

```sh
curl -s -X POST localhost:4896/api/conversations/assistant/messages \
  -H 'content-type: application/json' \
  -d '{"prompt":"what time is it in Tokyo?"}'
curl -s localhost:4896/api/conversations/assistant
```

## Telegram

Optional. Message [@BotFather](https://t.me/BotFather), send `/newbot`, and add
the token on the **Credentials** page (**Settings**, then **Credentials**) as a Telegram credential.

The harness then polls for messages alongside the web server — no public URL and no
tunnel, because it long-polls rather than taking a webhook. A direct chat that
sent a [link code](#link-codes) writes into that bot's chat, the same one the
browser shows. Telegram hears only the replies to what it sent.

`/new` clears the chat in place, like the browser's Clear button; `/stop` cancels the current reply. A message
sent while it is working is answered next rather than refused — and since phase 6
the browser behaves the same way, because being able to *show* a refusal is not a
reason to make someone retype what they wrote.

`/skills` lists the skills you can type. `/find-place <url>` — any `/name` —
loads that skill for the model before it reads your message, on every channel alike. A `/word` that is neither a command
nor a skill is answered with the list of what is, never handed to the model.

With no token the channel simply does not start.

## Discord

Optional, same shape. Create a bot in the
[Developer Portal](https://discord.com/developers/applications) and invite it
with the `bot` and `applications.commands` scopes. Add the token on the
**Credentials** page as a Discord credential.

A DM is answered once it has sent a [link code](#link-codes). In a server, only
messages that `@mention` the bot are read, and the Assistant answers them. That
is what keeps the privileged *Message Content* intent unnecessary, so the bot
never sees a channel's traffic it was not addressed in. `/new`, `/stop` and
`/skills` are slash commands. With no token the channel does not start.

## Link codes

One Telegram bot and one Discord bot serve the whole app. A link code picks
which of the app's bots a direct chat talks to.

On a bot's page, click **Link Telegram** or **Link Discord**. It shows a
six-digit code that names that bot, lasts 15 minutes and works once. Send
exactly that code to the Telegram or Discord bot. The chat is then linked to
that bot, and gets "Linked to {name}. Say hi."

A new code moves the chat to another bot. Five wrong guesses silence a chat for
15 minutes. Codes are kept in memory, so after a restart ask for a new one.
A code needs that platform's token on the Credentials page first.

A direct chat that never linked gets silence: no answer to its messages,
commands, taps or answers. Telegram groups are silent too, while in a Discord
server the Assistant still answers an `@mention`. A chat stored before link
codes keeps talking to the Assistant. A chat linked to an archived or deleted
bot is silent, never the Assistant, and answers again when the bot is restored.

## Credentials

**Settings** at the sidebar's foot opens the Credentials page
(`/settings/credentials`), which holds every key. Each key shows only its last four characters, never the whole
key. **Add credential** opens a dialog: pick a type, and that type's fields appear.

- **LLM**: a name, an endpoint, a model and a key. A bot's model is picked
  from the LLM credentials in **Edit bot**'s **Model** dropdown. A bot with
  none answers "Pick a model for this bot in Edit bot."
- **Custom**: a name, a website, a key, and the bots allowed to use it. This
  replaces the old Keys page. A bot can still ask for a key on a card in the
  chat, from any device.
- **Telegram** and **Discord**: a name and a token. There is at most one of
  each, and it serves no bots. Saving one starts that channel at once, and
  removing it stops it. A new token restarts only that channel.

Changes apply right away, with no restart. Each bot answers with its own model,
its LLM credential, and a bot with none makes no request. Temperature, timeout
and vision come from settings for every model. The compaction window is shared
too: `compaction.context_tokens`, or else the window Assistant's model's
endpoint reports. Compaction uses the model of the bot that spoke last in the chat.

Only a page on the Mac that runs the harness can add, edit or remove a
credential. The page saves straight to the harness's own port, which listens on
this Mac only. The page server forwards requests without the browser's address,
so the harness refuses any save that came through it, or from another device.
Anywhere else, such as on a phone, the page is read-only.

On start, the harness moves the keys in its per-machine settings file into the
keyring. For `make dev`, that file is `backend/config.local.json` and the
keyring is `~/.harness/secrets.json`. `llm.api_key` becomes the LLM credential
`model`, with the endpoint and model from settings, tied to no bot. `telegram.bot_token` and `discord.bot_token` become the Telegram and
Discord credentials.

The file then loses those keys and keeps every other value, including
`secrets.encryption_key`, the keyring's own key. It is rewritten readable by
its owner only. A key put back in the file later replaces only that
credential's key. The environment is no longer read for these keys:
`HARNESS_LLM__API_KEY`, `HARNESS_TELEGRAM__BOT_TOKEN` and
`HARNESS_DISCORD__BOT_TOKEN` are ignored.

With no LLM credential in the keyring, the harness still starts, and every chat
page shows a setup screen until one is saved. The screen asks for the API key,
saves it as the LLM credential `first_model` for Assistant, and opens the chat
with no restart. Only a page on the Mac that runs the
harness shows the form. Another device sees a note to finish setup there.
Automatic compaction stays off until the next start, because the harness asks
Assistant's model's endpoint for its context window only when it starts.

If you run `make dev`, the first start after this change moves your keys out of
`backend/config.local.json` into `~/.harness/secrets.json`. If you want a copy
of the file as it was, make one before that start.

## Desktop app

A Mac app for you and for friends who do not have the repo: one icon that
starts the harness and opens the chat in its own window. It has chat, bots,
skills and the PC; the dmg is about 260 MB. It carries its own Python and Deno.
The first time the PC starts it downloads the PC image (about 400 MB). Only the
`create-skill` skill ships. Apple Silicon only.

Every other MCP server is added on **Settings → MCP servers**: a name, a
command, its arguments, its settings and the names of the keys it needs. It
starts at once. A server that needs a key waits until the key is saved on the
Credentials page as a **Capability key**. The app does not carry Node or uv: a
server run with `npx` or `uvx` needs them installed, and the app finds them
through your Terminal's PATH. The app's PC is its own, beside `make dev`'s: its
runtime lives in `~/.cell-harness/msb`, a short path because microsandbox's
sockets must stay under 104 bytes.

```sh
make app      # desktop/dist-app/Cell Harness-0.1.0-arm64.dmg; needs uv, npm and the network to build
```

Upload the dmg to a GitHub release. It is signed ad-hoc, not by Apple, so the
first open says Apple could not verify it: in System Settings → Privacy &
Security, click **Open Anyway**, once. There are no automatic updates; a new
version is a new dmg.

On first start the app writes its settings file with a new encryption key, and
the chat window opens on the setup screen. It asks for the friend's own API
key, beside the endpoint and model from `desktop/config.json`, filled in and
open to change. Start saves the key in the keyring as
Assistant's model, and the chat opens in the same window. Everything the app keeps is in
`~/Library/Application Support/Cell Harness/`: the settings file
`config.local.json` (readable by its owner only), the keyring `secrets.json`,
the chats, and `logs/`. A
Telegram or Discord token is pasted on the Credentials page, which the menu-bar
icon's **Credentials…** opens; **Show Settings File** finds the file itself.
Closing the window keeps the harness running in the menu bar; **Quit** stops it.

The app listens on `127.0.0.1:4886` (harness) and `:4887` (pages) only, and
keeps its data apart from `make dev`'s `~/.harness`, so both run at once. To run
it from the checkout: `cd desktop && npm ci && npm run pages && npm start`. A
terminal that sets `ELECTRON_RUN_AS_NODE` (VS Code's extension host does) makes
Electron run as plain Node; unset it first. If the app sits inside a git
repository, the harness reads skills from that repository's `.agents/skills`
instead of the app's own.

## Layout

```
backend/harness/
  llm/          the model seam — messages, stream vocabulary, adapters/
  session/      the event log, its models, repository/, service, repair
  runtime/      the turn loop, its events, and hooks/ — the chain + native/<hook>/
  tools/        service, toolset, approvals, models/, client/, native/<tool>/
  sandbox/      the Runner seam + deno.py — runs a script, imports nothing else
  mcp/          the MCP client — one owning task per server, namespaced tools
  skills/       the catalog read from ranked roots, and the one `skill` tool
  runs/         a turn that outlives its connection — service, subscribe
  channels/     every way in and out — telegram/, discord/, web/, and per-chat state
  web/          server — the composition root (the HTTP surface is channels/web/)
  config/       one Settings: config.json + config.local.json + env
backend/tests/  unit/ and integration/
mcp-servers/    the capabilities we build — one uv project each, own tests
frontend/       Next.js chat — app/, components/, lib/
desktop/        the Mac app — Electron around the same pages; scripts/ builds the dmg
docs/           source teardowns + long-form rules
CLAUDE.md       project rules, loaded into every session
```

Subpackages arrive with the phase that needs them; the full intended layout is in
[DESIGN.md §3](./DESIGN.md).

Status: **phases 1–8 and 10 done.** Type `/find-place <url>` in the browser or
on a phone and the skill is loaded for the model; paste a public `SKILL.md` on
the Skills page in Settings and it is used next turn. Seven capabilities not in the
original arc have shipped since phase 7 — code mode, Instagram → Places, skills,
tool references, Discord, MCP Apps, markets — each recorded in
[PHASES.md §Status](./PHASES.md#status). Every phase in PHASES.md is a capability
you can demo. Next is phase 11, long conversations.
