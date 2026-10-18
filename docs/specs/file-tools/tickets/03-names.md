# 03 · Names that say what they return or decide

**Status.** done

**What to build.**
- `archive.py`: `extract` → `extract_archive`, `pack` → `pack_archive`, `unpack` → `unpack_entries`, `write_numbered` → `write_numbered_entries`, `numbered` → `padded_number`, `is_unpacked` → `should_unpack`, `files_in` → `files_in_order`.
- `image.py`: `SIGNATURES` → `MEDIA_TYPE_BY_SIGNATURE`.
- `chat_paths.py`: `files_in_chat` → `paths_in_chat`.
- `runtime/tool_run.py`: `_handed_over` → `_files_handed_over`, `_told` → `_with_hand_over_lines`.
- `tests/unit/test_send_file.py`: the helper `settled` → `session_after`.

**Checks.** The whole suite stays green. Grepping for each old name finds nothing.

**Blocked by.** 02
