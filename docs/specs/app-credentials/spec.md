# App credentials: a model for each bot, and MCP keys with their server

## Problem

Today a bot with no model of its own falls back to the Default model. One config switch says whether every model can see images. The context window is the Default model's, for all bots. MCP server keys sit on Credentials beside the app's own keys, and the app ships a built-in MCP server. The person wants each bot on a model they picked, and MCP kept apart from the app.

## What changes for you

1. On first start the setup screen asks for an address, a model name and a key. You save. Assistant now answers on that model.
2. You open another bot. It answers: "Pick a model for this bot in Edit bot."
3. You open **Edit bot**. A **Model** dropdown lists every LLM credential. You pick one and save. The bot's next answer comes from that model.
4. You click **New bot**. The **Model** dropdown is required. A bot made by asking in chat names its model too.
5. On Credentials you add an LLM credential. It has a **Can see images** switch. A bot on a model without it gets no images and no image tools.
6. In a chat you ask a bot to add your NVIDIA model. It shows a protected card with the fields filled in. You type the key on the card. The key never appears in the chat. Telegram and Discord tokens can be added the same way.
7. You remove an LLM credential that two bots use. Those bots now answer with the line from step 2.
8. Credentials lists no MCP keys. You open **MCP servers** and add a server. Its keys are typed there, in hidden fields, and saved with the server.
9. A fresh app has no MCP servers. You add each one, the bots' PC (`computer`) too, on **MCP servers**.

## Decisions

- **A bot with no model refuses, with one line.** There is no Default model. Dify falls back to a workspace default; the grill chose no fallback here.
- **Setup picks its model for Assistant.** So the chat works right after setup. Other bots stay unset.
- **Each LLM credential says whether it can see images.** OpenClaw marks each model `input: ["text", "image"]`, and only image models get images.
- **The context window is asked of each credential once.** It is asked on first use and kept until that credential changes. The config cap still wins.
- **A bot's model is picked in Edit bot.** Ticking bots on the credential dialog goes, so there is one place to set it.
- **MCP keys are saved with their server.** They go in the servers file, plain text, owner-only (0600). An MCP server is its own process, and its settings are its own.
- **There are no built-in MCP servers.** Every server is added on the MCP servers screen.
- **No upgrade code.** An old Default model is a plain LLM credential. Old MCP keys on Credentials are not read; type them again.

## Out of scope

- A model fallback when a bot's model fails.
- A bot switching its own model in a chat.
- Checking a key against its provider on save.
- Picking the model name from the provider's list.
- Removing the code in `mcp-servers/`. Only the config entry goes.

## How we will know it works

- Start a fresh app and finish setup. Assistant answers. A second bot answers the "Pick a model" line.
- Pick a model for that bot in Edit bot. Its next answer comes from that model, with no restart.
- Create a bot with no model, on the form or with `bot_create`. It is refused.
- Put a bot on a credential without **Can see images**, and attach an image. The request has no image and no `view_image` tool.
- Two bots on two credentials whose endpoints report different context windows each compact at their own window.
- Add an LLM credential from a chat card. The stored conversation holds its name, never its key.
- Remove an LLM credential. Its bots answer the "Pick a model" line.
- Add an MCP server with a key on MCP servers. It connects. The key is in the servers file, not on Credentials.
- Start with the committed `config.json`. No MCP server connects until one is added.
