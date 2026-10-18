# 02 · Seven names say what they give back

**Status.** open

**What to build.**
- `render_text` becomes `text_of`: in `llm/models/blocks.py`, the door's import and `__all__`, and every caller in `backend/harness/` and `backend/tests/` (about 18 files); `docs/mcp-apps.md` follows.
- `context_length` becomes `context_window_tokens` in `llm/adapters/context_window.py`, the adapters door, `web/server.py` and `tests/unit/test_context_length.py`.
- `context_window.py`'s `_Model` becomes `_ListedModel`.
- `_openai_frames.py`'s `_piece` becomes `_call_piece` (its parameter becomes `raw`) and `_pieces` becomes `_call_pieces`.
- `_openai_wire.py`'s `_extra_field` becomes `_extra_content_field` and `_wire_arguments` becomes `_sendable_arguments`.

**Checks.** `make lint` and `make test` green (1455 passed). A whole-word search for each old name in `backend/` and the docs (outside `docs/specs/`) finds nothing.

**Blocked by.** 01
