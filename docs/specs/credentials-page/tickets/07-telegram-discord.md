# 07 Telegram and Discord credentials

**Status:** open

**What to build.**

- The dialog's type picker gains Telegram and Discord, each asking for a name and a token. There is at most one of each.
- Adding one starts that channel at once, and removing it stops the channel. Replacing the token restarts only that channel.
- `ChannelGateway.register` returns a disposer, as the project's invariant asks, so a channel can leave while the harness runs.

**Checks.**

- A gateway test: a channel registered and started while the gateway runs receives messages, and its disposer stops it.
- A route test: a second Telegram credential is refused.
- By hand: add a Telegram token, and the bot answers a linked chat within seconds, with no restart.

**Blocked by.** 06
