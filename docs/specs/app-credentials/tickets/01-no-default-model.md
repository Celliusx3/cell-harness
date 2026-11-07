# 01 A bot with no model refuses, and setup picks its model for Assistant

**Status.** done

**What to build.** `CredentialModels.model_for` returns the bot's own LLM credential or a typed `NoModel`; the Default fallback and `DEFAULT_MODEL_CREDENTIAL` go. A turn on `NoModel` ends with the logged line "Pick a model for this bot in Edit bot." The Default model's removal refusal and `is_default_model` go. The setup screen saves an LLM credential and ties it to Assistant. Files: `web/bot_models.py`, `runtime/models.py`, `secrets/service.py`, `secrets/models/secret.py`, `web/routes/credentials.py`, `frontend/components/setup/SetupForm.tsx`, `frontend/lib/credentials.ts`.

**Checks.** Integration with a fake OpenAI-compatible server: after setup, Assistant's turn reaches the server. A second bot's turn reaches nothing, and its stored conversation ends with the line. Removing Assistant's credential makes its next answer the line.

**Blocked by.** none
