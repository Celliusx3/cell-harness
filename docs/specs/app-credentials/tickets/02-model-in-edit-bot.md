# 02 A bot's model is picked in Edit bot

**Status.** done

**What to build.** The bot routes accept `model_credential` (an LLM credential's name, or `null`), and refuse a name that is not an LLM credential. **Edit bot** gets a **Model** dropdown of the LLM credentials. The credential dialog stops offering bot ticks for an LLM credential. Files: `bots/ties.py`, `bots/service.py`, `web/routes/bots.py`, `frontend/components/bots/BotForm.tsx`, `frontend/components/credentials/CredentialDialog.tsx`.

**Checks.** Integration: setting a bot's model by the route makes its next turn reach that credential's server. A Custom credential's name is refused with 422. The dialog for an LLM credential has no bot list.

**Blocked by.** 01
