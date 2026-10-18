# 02 · The model package has a door, and the app uses it

**Status.** done

**What to build.**
- `backend/harness/llm/__init__.py` exports, with `__all__`, exactly the names other packages import today: from `messages`, `ApplicationMessage`, `AssistantMessage`, `Block`, `ExtraContent`, `Image`, `Message`, `SystemMessage`, `Text`, `ToolCall`, `ToolMessage`, `ToolReference`, `ToolSpec`, `UserMessage`, `images_of`, `render_text`; from `stream`, `CONTEXT_WINDOW_EXCEEDED`, `Completed`, `Failed`, `StreamEvent`, `TextChunk`, `ToolCallChunk`, `Usage`; from `client`, `LLMClient`.
- Every file under `backend/harness/` outside `llm/` that imports from `harness.llm.messages`, `harness.llm.stream` or `harness.llm.client` imports from `harness.llm` instead (20 files). Files inside `llm/` keep importing each other directly.

**Checks.** `make lint` and `make test` green (1455 passed). `git grep -nE "from harness\.llm\.(messages|stream|client) import" -- backend/harness ':!backend/harness/llm'` finds nothing.

**Blocked by.** 01
