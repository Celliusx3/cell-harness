# 04 · Each request names its chat, so OpenRouter keeps one provider

**Status.** open. Build it only if it is approved with the spec.

**What to build.** The OpenAI adapter's request body gains `session_id`, set to the chat's session id. OpenRouter then keeps the chat's requests on one provider from the first request. The id reaches the adapter as one more explicit argument from the turn.

A provider that refuses the unknown field fails the turn. So the field is sent only when the endpoint is OpenRouter's, read from the credential's base URL in one place.

Files: `llm/adapters/openai/_request.py`, `llm/adapters/openai/client.py`, `llm/client.py`, `runtime/turn.py`, and their tests.

**Checks.** A unit test builds a request for an OpenRouter base URL. The body has `session_id` equal to the chat's id. For another base URL it has none. A run against OpenRouter shows `cached_tokens` above zero from the second step on. `make lint` and `make test` stay green.

**Blocked by.** 01
