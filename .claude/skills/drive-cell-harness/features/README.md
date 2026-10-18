# Feature map

One file per thing a person can see in the browser chat. Add a file when a feature ships.

- [chat.md](chat.md): sending a message and reading the reply
- [tool-cards.md](tool-cards.md): a tool call as a card, including `run_subagent` helpers
- [files.md](files.md): files you attach, images the model sees, and the files a bot unpacks, packs, views and hands back
- [approvals.md](approvals.md): a card that asks before a write runs
- [skills.md](skills.md): the Skills page
- [bots.md](bots.md): bots, each with its own instructions and one chat, made by describing one to Bot builder or by asking any bot
- [groups.md](groups.md): two to six bots in one chat, taking turns, each turn under the bot's name with its tool calls folded
- [bot-messages.md](bot-messages.md): a bot messages another with `message_bot`, and the answer wakes it in its own chat
- [secrets.md](secrets.md): a card that saves an API key the model never sees, the Keys page, each bot's keys, and the fetch that uses one
- [computer.md](computer.md): the Computer page: the shared computer's live screen, control on open, a terminal and files
- [hand-over.md](hand-over.md): a "Needs you" card when a bot needs a step only you should do on the computer
