# 01 · The streamed-line rules and the system message are pinned

**Status.** done

**What to build.** Tests for promises nothing checks today, written against the code as it is, in a new `backend/tests/unit/test_openai_stream_edges.py` (`test_openai_tools.py` is already near the line cap):
- an `index` sent as the text `"0"` is treated as no index; an `id` sent as a number is ignored and the call gets `call_<slot>`;
- a token count sent as text gives no usage; usage from an earlier line is kept when a later line has none;
- `content: ""` gives no text chunk; `{"error": null}` is not an error; lines after `[DONE]` are ignored;
- a later `extra_content` for the same call replaces the earlier one;
- in `backend/tests/unit/test_openai_request.py` (moved there in the cleanup, so each file has one subject): the request goes to `<base_url>/chat/completions` with `Authorization: Bearer <key>` and the full body, and a `SystemMessage` is wired as exactly `{"role": "system", "content": ...}`.

**Checks.** Every new test passes on the code as it is; `make lint` and `make test` stay green.

**Blocked by.** none
