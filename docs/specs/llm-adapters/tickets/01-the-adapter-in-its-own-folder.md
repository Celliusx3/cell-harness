# 01 · The OpenAI adapter in its own folder, its models apart

**Status.** open

**What to build.** The files in `backend/harness/llm/adapters/` move into `adapters/openai/`. No logic changes. `openai/__init__.py` and `openai/models/__init__.py` are one-line docstrings.

- `openai/client.py` ← `openai.py` (`OpenAIClient`, `ImageReader`, `_image_bytes`) and `context_window.py` (`context_window_tokens`, `_ListedModel`, `_Listing`): every call the adapter makes to OpenAI, in one file
- `openai/models/chunk.py` ← `Frame`, as `Chunk` (field `pieces` → `tool_deltas`)
- `openai/models/tool_delta.py` ← `CallPiece`, as `ToolDelta`
- `openai/_request.py` ← `_openai_wire.py` plus `_request_body` from `openai.py`; `wire_messages` → `openai_messages`, `_wire_message` → `_openai_message`, `wire_tool` → `openai_tool`, `_request_body` → `request_body`
- `openai/_streaming.py` ← `_openai_frames.py` without its dataclasses; `frame_of` → `chunk_of`, `_call_pieces` → `_tool_deltas`, `_call_piece` → `_tool_delta`
- `openai/_tool_calls.py` ← `_openai_calls.py`; `ToolCallAccumulator` → `ToolCallAssembler`
- `openai/_errors.py` ← `_errors.py` (`failure_code`)

`adapters/__init__.py` keeps exporting `ImageReader`, `OpenAIClient` and `context_window_tokens`, from `openai.client`. Tests follow the new paths and names; `tests/unit/test_openai_frames.py` becomes `tests/unit/test_openai_streaming.py`. `docs/compaction.md` follows.

**Checks.** `make lint` and `make test` green (1455 passed). A whole-word search for each old name and old module path outside `docs/specs/` finds nothing. Break: import `harness.llm.adapters.openai._request` from `harness/web/server.py`; the layering test fails.

**Blocked by.** none
