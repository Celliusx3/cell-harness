# 02 · No test-only shortcut, and the system message is sent by name

**Status.** open

**What to build.**
- `llm/messages.py`: delete the `ToolMessage.text` property; the 11 test sites that read it call `render_text(....content)`.
- `llm/adapters/openai_wire.py`: `wire_message` becomes private; the `model_dump()` fallback becomes an explicit `SystemMessage` branch, and anything else is refused with `assert_never`; bare `dict` in signatures is spelled `dict[str, JsonValue]`. `tests/unit/test_tools_selected.py` goes through `wire_messages`.
- `llm/adapters/__init__.py` and `llm/client.py`: the docstrings say what is true (the composition root imports an adapter; the client is an abstract base).

**Checks.** The suite stays green, including ticket 01's system-message test. Break: send the system message with role `"user"`; ticket 01's test fails.

**Blocked by.** 01
