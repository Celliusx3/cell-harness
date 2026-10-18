# 01 Restore the general work from the stash

**Status.** done

**What to build.** Bring back from `stash@{0}` everything that is not the comic server: images in tool results (`backend/harness/runtime/images.py`, `session/images.py`, `llm/messages.py`, the OpenAI adapter), the file store and `extract_archive` / `make_archive` / `send_file` (`backend/harness/files/`, `tools/native/files/`), the Gemini fixes, the bridge refusing image tools, the frontend attachments, and their tests. In `backend/config.json`: `vision`, `files` and the `photocraft` server, not `comic`. Leave out `mcp-servers/comic`, `.agents/skills/translate-comic`, `.claude/skills/translate-comic`, the comic `Makefile` line and the person's own files (`episode-118.cbz`, `decisions.tsv`, `.audit/`, the screenshot).

**Checks.** `make test` reports 1377 passed; `make lint` is clean; no `comic__` tool is configured.

**Blocked by.** none
