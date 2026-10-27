# 07 Telegram and Discord credentials

**Status:** done, except the by-hand check with a real token

**What to build.**

- The dialog's type picker gains Telegram and Discord, each asking for a name and a token. There is at most one of each.
- Adding one starts that channel at once, and removing it stops the channel. Replacing the token restarts only that channel.
- `ChannelGateway.register` returns a disposer, as the project's invariant asks, so a channel can leave while the harness runs.

**Checks.**

- A gateway test: a channel registered and started while the gateway runs receives messages, and its disposer stops it.
- A route test: a second Telegram credential is refused.
- By hand: add a Telegram token, and the bot answers a linked chat within seconds, with no restart.

**Blocked by.** 06

**Notes.**

- The by-hand check has not run: it needs a real Telegram token and a linked chat, which wait for ticket 08. A fake token was added and removed by hand on port 4986. The channel started, Telegram refused the token, and the log never showed it.
- A refused token stops its channel, and the channel stays on the gateway until the token is replaced or removed. Replacing or removing it does not raise.
- A reply already being sent when its platform leaves goes to the platform that left. That platform refuses it, and the failure is logged once.
