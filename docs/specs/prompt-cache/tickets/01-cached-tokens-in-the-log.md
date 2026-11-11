# 01 · Each reply's usage records its cached input tokens

**Status.** done

**What to build.** `Usage` gains `cached_input_tokens: int | None`. `None` means the provider did not report it, and old logs read as `None`. The OpenAI adapter reads it from the usage block's `prompt_tokens_details.cached_tokens`. `input_tokens` keeps its meaning, all input tokens cached or not, so the context size count does not change.

Files: `llm/models/stream.py`, `llm/adapters/openai/_streaming.py`, and their tests.

**Checks.**

- A unit test feeds the adapter a usage line with `prompt_tokens: 10339` and `cached_tokens: 10318`. The `Completed` usage carries both numbers.
- A line without `prompt_tokens_details` gives `None`.
- An integration test runs one turn on a fake model that reports cached tokens. The logged `assistant/message` usage has them.
- An old log line without the field still loads.
- `make lint` and `make test` stay green.

**Blocked by.** none
