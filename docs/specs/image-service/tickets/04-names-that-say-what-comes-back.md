# 04 · Names that say what comes back

**Status.** done

**What to build.**
- `session/derive.py`: `without_images(messages)`, called by `runtime/service.py` and `runtime/compaction/service.py` in place of `newest_images_only(…, kept=0, kept_bytes=0)`.
- `llm/adapters/openai_wire.py`: `_shown` becomes `_readable_images`, `_tool_images` becomes `_tool_images_message`, `_with_images` becomes `_content_with_images`, and the `images` parameter that holds bytes by hash becomes `image_bytes` (also in `openai.py`).
- `runtime/tool_run.py`: `_shown` becomes `_with_result_images`.
- `channels/web/routes.py`: `_names_image` becomes `_log_shows_image`.

**Checks.** The whole suite stays green, and the frontend typecheck stays clean. Breaking `without_images` so it keeps an image turns a compaction test red. Grepping for the old names finds nothing.

**Blocked by.** 02
