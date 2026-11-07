# 04 Each LLM credential says whether it can see images

**Status.** open

**What to build.** `ModelDetails.vision: bool`, and `ModelChoice` carries it. A turn on a text-only model gets no images, and its toolset leaves out `view_image`. `llm.vision` leaves `LLMSettings`. The credential form and the setup screen get a **Can see images** switch. Files: `secrets/models/details.py`, `runtime/models.py`, `web/bot_models.py`, `web/runtime.py`, `frontend/components/credentials/CredentialFields.tsx`.

**Checks.** Integration with the fake server: a text-only bot's request has no image block and no `view_image` schema, with an image attached. A vision bot's has both.

**Blocked by.** 01
