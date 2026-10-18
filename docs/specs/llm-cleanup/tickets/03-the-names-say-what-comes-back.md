# 03 · The names say what comes back

**Status.** done

**What to build.**
- `llm/adapters/errors.py`: `classify` becomes `failure_code`; callers in `llm/adapters/openai.py`, `tests/unit/test_overflow_classify.py` and `docs/compaction.md` follow.
- `llm/adapters/openai_calls.py`: `ToolCallAccumulator.drain` becomes `tool_calls`; its caller in `openai.py` follows.
- `llm/adapters/models.py` moves to `llm/adapters/context_window.py`; `web/server.py` and `tests/unit/test_context_length.py` follow.

**Checks.** The suite stays green. Break: a search for `classify`, `drain` and `adapters.models` in `backend/` and `docs/` finds nothing.

**Blocked by.** 01
