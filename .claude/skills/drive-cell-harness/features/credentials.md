# Credentials

The harness's own keys: the model's API key and the Telegram and Discord bot tokens. They are not the Keys page's keys, which bots save and use.

## Sub-features

- Each row shows its path (`llm.api_key`), its description, and its state: "saved, ends in …a1b2", "saved", "not set", or "set by HARNESS_…".
- On the Mac that runs the harness, each row gets a password box. A saved key gets Remove, except the model's API key, which can only be replaced. The header gets Save.
- Save goes straight to the harness's own address, never through the page server. The header then reads "Saved. Restarting the harness…", and "Saved and applied." once a new harness process answers.
- If a reply is being written, Save asks "A reply is being written and will stop. Save and restart?"; Cancel reads "Nothing was saved."
- Anywhere else the page is read-only and says "Change credentials on the Mac that runs the harness."

## How to get to it (user POV)

Click the lock icon in the sidebar, or go to `/credentials`. In the Mac app, the menu-bar icon's "Credentials…" opens it.

## Driving it with Playwright MCP

Use fake keys in a scratch config, never the person's own. Run the backend with `HARNESS_CONFIG_LOCAL` pointing at a scratch file. Add `--reload --reload-dir <scratch folder> --reload-include config.local.json`, so a save restarts it. Open `/credentials`, type into "New value for telegram.bot_token", click "Save", and wait for "Saved and applied.". A save sent through the page server, for example `curl -X PUT localhost:4997/api/credentials`, must answer 403.
