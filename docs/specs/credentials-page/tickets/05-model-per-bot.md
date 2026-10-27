# 05 A model per bot

**Status:** open

**What to build.**

- A turn uses its bot's LLM credential: that endpoint, model and key. A bot with none uses the Default model credential.
- Compaction uses the model of the bot whose chat it compacts.
- The runtime asks for a bot's model on each turn, so an edited or new credential applies to the next turn with no restart.
- Files: `harness/runtime/turn.py`, `harness/runtime/compaction/service.py`, the runtime's model choice, and `harness/web/runtime.py`.

**Checks.**

- A runtime test with two scripted model clients: Trader's turn goes to Trader's client and Chef's to the default one.
- After editing Trader's credential, the next turn goes to the new client.

**Blocked by.** 03
