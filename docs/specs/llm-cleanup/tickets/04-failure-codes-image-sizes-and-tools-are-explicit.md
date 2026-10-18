# 04 · Failure codes, image sizes and the tools list are explicit

**Status.** done

**What to build.**
- `llm/stream.py`: `FailureCode = Literal["context_window_exceeded"]`; `CONTEXT_WINDOW_EXCEEDED` is typed as it; `Failed.code: FailureCode | None`. `llm/adapters/errors.py`'s `failure_code` returns `FailureCode | None`.
- `llm/messages.py`: `Image.size` has no default; every test that builds an `Image` passes its size.
- `llm/client.py` and `llm/adapters/openai.py`: `tools` keeps `| None` and loses `= None`.

**Checks.** The suite stays green. Break: `Failed(reason="x", code="context_window_exceded")` must raise; a test asserting it is added.

**Blocked by.** 03
