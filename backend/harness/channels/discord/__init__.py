"""Discord, via the gateway websocket and the interactions API.

channel.py   `DiscordChannel` — receiving, sending, and the two slash commands

**Setting up the bot.** Developer Portal → New Application → Bot → Reset Token;
the token goes in `config.local.json` under `discord.bot_token`. Invite it with
an OAuth2 URL carrying the `bot` and `applications.commands` scopes and the
Send Messages, Send Messages in Threads and Read Message History permissions.
**No privileged intents** — see `channel.py` on why none is requested. The
`/new` and `/stop` commands are registered globally on every start and can take
up to an hour to appear in the picker the first time.
"""
