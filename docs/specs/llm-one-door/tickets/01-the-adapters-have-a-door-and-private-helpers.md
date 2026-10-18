# 01 · The adapters have a door, and their helpers are private

**Status.** done

**What to build.**
- `backend/harness/llm/adapters/`: `errors.py`, `openai_calls.py`, `openai_frames.py` and `openai_wire.py` become `_errors.py`, `_openai_calls.py`, `_openai_frames.py` and `_openai_wire.py`; the imports between them and in `openai.py` follow.
- `backend/harness/llm/adapters/__init__.py` exports `ImageReader`, `OpenAIClient` and `context_length` with `__all__`.
- `backend/harness/web/server.py` and `web/runtime.py` import through it.
- Tests that import those files by name follow (`test_failure_code.py`, `test_openai_frames.py`, `test_openai_request.py`, `test_tools_selected.py`, and any other the suite finds).

**Checks.** `make lint` and `make test` green (1455 passed). Break: import `harness.llm.adapters._openai_wire` from `harness/web/server.py`; `test_no_package_imports_another_package_s_private_module` fails.

**Blocked by.** none
