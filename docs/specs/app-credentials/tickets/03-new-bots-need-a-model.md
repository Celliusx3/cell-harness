# 03 A new bot is made with its model

**Status.** done

**What to build.** **New bot** requires the **Model** dropdown. `bot_create` takes a required `model` naming an LLM credential, and returns a `Failure` that lists the saved ones for an unknown name. Files: `tools/native/bots/create.py`, `tools/native/bots/models.py`, `bots/service.py`, `web/routes/bots.py`, `frontend/components/bots/BotForm.tsx`.

**Checks.** Integration: creating a bot with no model is 422. `bot_create` with an unknown model returns `error: …` with the saved names. With a known one, the new bot's first turn reaches that model.

**Blocked by.** 02
