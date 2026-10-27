# Credentials

## Problem

Every bot uses the same model key, and one Telegram token answers everyone as the Assistant. You cannot give Trader a stronger model, or send a friend to Chef on Telegram. Keys are split between a hidden settings file and the Keys page.

## What changes for you

1. You open the Credentials page from the sidebar. It lists every key: model keys, the Telegram and Discord tokens, and the keys bots use on websites.
2. Each key shows its name, its type, the bots it serves, and its last four characters.
3. You click "Add credential". A dialog asks for a type: LLM, Telegram, Discord or Custom. Its fields change with the type.
4. You add an LLM credential named "Trader's model" with an endpoint, a model and a key, and tick Trader. Trader's next reply uses it at once. Bots without an LLM credential use the Default model.
5. You add the Telegram credential with the token BotFather gave you. The Telegram bot starts at once.
6. On Chef's page you click "Link Telegram". It shows a code like 482913, valid for 15 minutes.
7. Your friend sends that code to your Telegram bot. From then on, their chat talks to Chef.
8. A stranger who messages the Telegram bot without a code gets no answer. Telegram groups get no answer.
9. In a Discord server, the bot still answers @mentions as the Assistant. Discord direct messages link with a code, as Telegram's do.
10. On your phone, the page is read-only. Keys are added and changed on the Mac that runs the harness.

## Decisions

- Every key is a typed credential with a name you choose. n8n and AstrBot pick the type first and then show that type's fields.
- An LLM credential can serve several bots, and each bot uses at most one. Bots without one use the Default model. Rakazo and Dify fall back to a default the same way.
- One Telegram bot and one Discord bot serve the whole app. A link code chooses which bot a person talks to, as Rakazo's link codes do.
- A direct chat that never sent a code gets silence, as Rakazo's does. Telegram groups stay silent, as Rakazo keeps groups to iMessage.
- Discord server channels keep answering @mentions as the Assistant, as they do today.
- Chats that talk to the Assistant today stay linked to it, so nothing in use goes silent.
- A link code lasts 15 minutes, as Rakazo's do, and a new code moves a chat to another bot. Codes are kept in memory, so a restart asks for a new code.
- Credentials are sealed in the existing encrypted keyring, beside today's saved keys. Rakazo and Hermes keep provider keys out of plain config.
- The keys in the settings file move into the keyring on the first start after this ships. The model key becomes the Default model, and the file stops holding keys.
- A change takes effect at once, with no restart. AstrBot starts a new platform the moment it is saved.
- Only a page on the Mac that runs the harness can add or change a credential, as PR #43's guard does. A bot asking for a key on a card in the chat still works from any device.
- A key never leaves the harness in full. The page sees only its last four characters.

## Assumptions

- A bot uses one LLM credential at a time. Ticking it in another LLM credential moves it there.
- Chats that already talk to the Assistant stay linked to it.

## Out of scope

- Several Telegram or Discord bots, or one per harness bot.
- Telegram groups, and linking a whole group.
- Testing a key with its provider before it is saved.
- Server keys inside the MCP server settings.
- A login.

## How we will know it works

- Open Credentials. Today's saved keys show as Custom credentials, and the old model key shows as the Default model.
- Add an LLM credential for Trader. Trader's next reply comes from that model, and Chef's from the Default.
- Add the Telegram token. The Telegram bot answers a linked chat within seconds, with no restart.
- Click "Link Telegram" on Chef's page, and send the code from Telegram. That chat now talks to Chef.
- Message the Telegram bot from an account that never linked. Nothing answers.
- @mention the bot in a Discord server. The Assistant answers.
- Open the page from a phone, or send a save through the page server. Saving is refused.
- Remove the Telegram credential. The Telegram bot stops answering within seconds.
