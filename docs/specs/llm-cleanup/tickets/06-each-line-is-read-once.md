# 06 · Each streamed line is read once, into a named shape

**Status.** done

**What to build.**
- New `llm/adapters/openai_frames.py`: frozen dataclasses `CallPiece(index, id, name, arguments, extra_content)` and `Frame(text, pieces, usage, failed)`, and a pure `frame_of(payload)` carrying today's exact tolerance (the `isinstance` checks that live in `openai.py` and `openai_calls.py` today, and the `extra_content` check with its warning).
- `llm/adapters/openai_calls.py`: `ToolCallAccumulator.add` takes `Sequence[CallPiece]`; `_joined` and `_slot` read typed fields with no `isinstance`.
- `llm/adapters/openai.py`: `_usage`, `_delta` and `_text` are gone; the loop reads a `Frame`; the request body is built by a pure `_request_body(...)`.
- New `tests/unit/test_openai_frames.py`: `frame_of` tested by handing it values, no HTTP.

**Checks.** The suite stays green, including every ticket 01 and 05 test. Break: let `frame_of` accept an index sent as text; a ticket 01 test fails.

**Blocked by.** 03, 04, 05
