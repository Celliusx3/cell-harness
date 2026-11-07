# 07 An LLM, Telegram or Discord credential is added from a chat card

**Status.** open

**What to build.** `ask_for_secret` gains `kind`: `custom` (today's card), `llm` (with address, model and vision for the card to show filled in), `telegram` or `discord`. The card shows those fields, editable, and the hidden key field. The save stores that kind of credential and gives the waiting call only its name. Files: `tools/native/secrets/models.py`, `tools/native/secrets/tools.py`, `web/routes/secret_card.py`, `frontend/components/answer/SecretRequest.tsx`.

**Checks.** Integration with a scripted model: `ask_for_secret` with `kind: llm` stores an LLM credential. The stored conversation holds its name and never its key. `fetch_with_secret` with that name returns `error: …` and sends nothing.

**Blocked by.** 04
