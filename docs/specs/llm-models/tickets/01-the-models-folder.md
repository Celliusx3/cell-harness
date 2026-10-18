# 01 · The vocabulary sits in a models folder, one file per subject

**Status.** done

**What to build.** `backend/harness/llm/messages.py` and `backend/harness/llm/stream.py` are replaced by `backend/harness/llm/models/`:
- `__init__.py`: a one-line docstring only.
- `tools.py`: `ExtraContent`, `ToolCall`, `ToolSpec`.
- `blocks.py`: `Text`, `ToolReference`, `Image`, `Block`, `render_text`.
- `messages.py`: `SystemMessage`, `UserMessage`, `ApplicationMessage`, `AssistantMessage`, `ToolMessage` (with its validator), `Message`, `images_of`.
- `stream.py`: `Usage`, `TextChunk`, `ToolCallChunk`, `Completed`, `FailureCode`, `CONTEXT_WINDOW_EXCEEDED`, `Failed`, `StreamEvent`.

Each class moves unchanged, with its docstring. Every import inside `backend/harness/llm/` follows (the door, `client.py`, the adapters). Docs that name the old paths follow: `PHASES.md`, `docs/mcp-tool-scaling.md`, `mcp-servers/README.md`.

**Checks.** `make lint` and `make test` green (1455 passed). A search for `harness.llm.messages`, `harness.llm.stream`, `llm/messages.py` and `llm/stream.py` outside `docs/specs/` and `DESIGN.md` finds nothing.

**Blocked by.** none
