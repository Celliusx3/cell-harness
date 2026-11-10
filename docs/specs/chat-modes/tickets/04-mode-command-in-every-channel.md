# 04 · `/mode` switches the chat in Telegram, Discord and the browser

**Status.** done

**What to build.** A `/mode` command that takes `ask`, `auto` or nothing. With a mode it calls `RunService.set_mode` and answers "Mode: Auto." With nothing it answers the current mode. Any other word answers which words it takes. The command needs an argument, so the commands module gets a typed value for it beside `Command`.

Telegram parses it. Discord registers it as a slash command with a choice. The browser's send route handles `/mode` before it looks for a skill. `COMMANDS` names `/mode`. Files: `channels/commands.py`, `channels/telegram/commands.py`, `channels/discord/channel.py`, `channels/gateway.py`, `channels/web/routes.py`.

**Checks.** Unit tests for parsing `/mode`, `/mode auto` and `/mode yes`. An integration test through the gateway: `/mode auto` makes the next protected call run, and `/mode` answers "auto". In the browser, sending `/mode auto` switches the chat and starts no turn. `make lint` and `make test` stay green.

**Blocked by.** 01
