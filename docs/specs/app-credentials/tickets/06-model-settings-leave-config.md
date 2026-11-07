# 06 The app starts with no model settings in config

**Status.** done

**What to build.** `llm.base_url` and `llm.model` leave `LLMSettings` and `config.json`; `temperature` and `timeout_seconds` stay. `load()` stops checking a model. `shipped_model` goes, so the setup screen and credential form start blank. Docs and `config.local.example.json` follow. Files: `config/sections.py`, `config/settings.py`, `web/server.py`, `web/routes/credentials.py`, `backend/config.json`.

**Checks.** Integration: the app starts from a config with no `llm.base_url` or `llm.model`. `grep -rn "settings.llm.model\|settings.llm.base_url" backend/harness` finds nothing.

**Blocked by.** 01, 04, 05
