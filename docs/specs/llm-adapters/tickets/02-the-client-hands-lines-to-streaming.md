# 02 · The client hands the streamed lines to the streaming file

**Status.** open

**What to build.**
- `openai/_streaming.py` gains `chunks_of(lines: AsyncIterator[str]) -> AsyncIterator[Chunk]`, which carries today's line rules out of the client: only `data: ` lines, stop at `[DONE]`, skip a line that is not JSON or not an object, each with today's warning.
- `Chunk.failed: bool` becomes `error: str | None`, holding the line as sent when its `error` is truthy, so the client's `Failed` keeps today's reason and code.
- `OpenAIClient.stream_completion` reads `chunks_of(response.aiter_lines())` and is under a complexity of 10.
- Every logger in `openai/` is `harness.llm.openai`.
- The endpoint address and the `Authorization` header are built in one place in `client.py`, used by both `stream_completion` and `context_window_tokens`.
- `tests/unit/test_openai_streaming.py` tests `chunks_of` by handing it lines.

**Checks.** `make lint` and `make test` green (1455 passed, plus the new streaming tests). `uv run ruff check harness/llm --select C901` reports nothing. Break: let `chunks_of` keep reading past `[DONE]`; a test fails.

**Blocked by.** 01
