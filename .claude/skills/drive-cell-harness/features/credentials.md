# Credentials

Every key the harness holds, on one page: model keys (LLM), the Telegram and Discord tokens, and the keys bots use on websites (Custom). The page sees only a key's last four characters. Changes apply at once, with no restart.

## Sub-features

- Rows sit under LLM, Telegram, Discord and Custom. Each shows its name, what it is for ("<model> at <host>", or a Custom key's host), and its bots or "no bots".
- A key shows "ends in …a1b2", or "saved" when it is under eight characters.
- `default_model` is marked "Default model". Bots with no LLM credential use it. It has Edit but no Remove.
- On the Mac that runs the harness, the header has "Add credential" and each row has Edit and Remove. Anywhere else the page is read-only and says "Change credentials on the Mac that runs the harness."
- "Add credential" opens a dialog: "Pick a type, then fill in its fields." Type offers Custom, LLM, Telegram and Discord, without a platform already saved.
- LLM asks for Name, Endpoint, Model, Key and Bots. Custom asks for Name, Website, "The site takes the key", Key and Bots. Telegram and Discord ask for Name and Token, and serve no bots.
- A bot uses one LLM credential: ticking it in another moves it there. Edit fixes the type and name, and an empty key keeps the saved one.
- Remove asks first: "Remove <name>? The bots it serves lose it.", or for a platform "Remove <name>? Its bot stops answering."
- Saving a Telegram or Discord token starts that channel, and removing it stops it. A new token restarts only that channel.
- A bot's page has "Link Telegram" and "Link Discord" under "Chats on other apps". Each shows a six-digit code, who it links to, and "Expires in m:ss".
- With no token saved, a link button shows "Telegram has no token yet. Add the Telegram token on the Credentials page first."

## How to get to it (user POV)

Click the lock icon in the sidebar, or go to `/credentials`. In the Mac app, the menu-bar icon's "Credentials…" opens it. The link buttons are on a bot's page: "Edit bot" in its chat header.

## Driving it with Playwright MCP

Add only fake keys. The launch's scratch `HARNESS_CONFIG_LOCAL` gives the copy only the model's key, and the copy's keyring is `$RUN/harness/secrets.json`. Never point either at the person's own files.

`browser_navigate` to `/credentials` and wait for "Add credential". It shows only once the page reaches the harness on port 4996 directly. Click it, `browser_select_option` the type in "Type", and type into each field by its label. A Custom "Website" must be a bare `https://` origin. Tick bots by name, then click "Save". The new row ends in the last four characters you typed.

To remove one, click its "Remove", then `browser_handle_dialog` with `accept: true`. A save through the page server must answer 403: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:4997/api/credentials`.

## Gotchas

A fake Telegram token starts the channel, and Telegram refuses it. The log says `telegram channel registered`, then `telegram channel stopped: Telegram refused the bot token`. Remove it when done; the Doctor's grep still finds that line, from the fake token. A fake LLM key ticked to a bot makes that bot's turns fail; untick the bot or remove the key. Link codes live in memory, so a restart voids every code shown.
