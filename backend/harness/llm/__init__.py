"""The provider-neutral model seam — phase 1.

`LLMClient` is what the loop depends on; a concrete provider lives under
`adapters/` and nothing outside this package imports one. The vocabulary the
loop moves — `Message`, `ContentBlock`, `ToolCall`, `StreamChunk` — is declared
here rather than in `session/`, because it is what a *request* is made of; what a
*session* records is a separate (and durable) concern.

The one contract every adapter owes: a stream yields exactly one terminal event
(`Completed` or `Failed`). Callers rely on it to know a turn is done, so an
adapter that can end silently will hang the loop.
"""
