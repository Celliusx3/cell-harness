# 02 · Channel delivery and the TypeScript printer under the limit

**Status.** done

**What to build.**
- `backend/harness/channels/replies.py`: `Replies.deliver` (12) moves its per-event checks into the helpers that act on them: skipping an empty reply, skipping an app link when there is no public URL or no app, and asking every pending call.
- `backend/harness/tools/native/code/typescript.py`: `_render` (12) moves its `$ref` branch and its `type` branch into two helpers.

Behaviour, messages and printed types stay exactly as they are.

**Checks.** `make lint` and `make test` green. `uv run ruff check harness/channels/replies.py harness/tools/native/code/typescript.py --select C901` reports nothing.

**Blocked by.** none
