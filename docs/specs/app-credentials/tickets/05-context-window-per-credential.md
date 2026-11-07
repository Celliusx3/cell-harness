# 05 Each LLM credential has its own context window

**Status.** open

**What to build.** `CredentialModels` asks a credential's endpoint for its window on first use, cached with the choice by version. `ModelChoice.context_tokens` carries it, and compaction reads it there. `compaction.context_tokens` in config still caps it. The startup `_resolve_context_tokens` goes. Files: `web/bot_models.py`, `runtime/models.py`, `runtime/compaction/service.py`, `runtime/service.py`, `web/server.py`.

**Checks.** Integration: two fake servers report 8k and 32k windows. Each bot compacts at its own window. The window is asked once over two turns.

**Blocked by.** 01
