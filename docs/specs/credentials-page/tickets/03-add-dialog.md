# 03 Add, edit and remove: Custom and LLM

**Status:** open

**What to build.**

- "Add credential" opens a dialog. The type picker offers Custom and LLM in this ticket, and each type shows its own fields.
- Custom asks for a name, website, key and bots. LLM asks for a name, endpoint, model, key and bots.
- Each row gets Edit and Remove. An empty key field on Edit keeps the saved key.
- A bot gains `model_credential`, the id of its LLM credential, or none. Ticking a bot in an LLM credential moves it there.
- Custom bots are stored as today, in each bot's allowed keys.
- `POST`, `PATCH` and `DELETE` on `/api/credentials` keep PR #43's guard: only a page on this Mac, straight to the harness.

**Checks.**

- Route tests:
  - a Custom and an LLM credential are created, edited and removed
  - ticking Trader in a second LLM credential moves it
  - a save through a proxy or from a foreign origin is refused
- By hand: add both kinds in the dialog, and they show in the list with their bots.

**Blocked by.** 02
