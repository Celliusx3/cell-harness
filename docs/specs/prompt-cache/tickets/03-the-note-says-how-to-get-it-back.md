# 03 · The note in place of a hidden image says how to get it back

**Status.** open

**What to build.** `IMAGE_NOT_SHOWN` in `prompts.py` becomes: "This image was removed to reduce the request size and is no longer visible. Do not make claims about its contents from memory. If needed, retrieve it again with an available tool or ask the user to attach it again." Brackets stay around it as today.

Add its row to `docs/prompt-failures.md`. The failure on record is the 2026-10-16 run, where a model translated pages it never saw. The wording follows opencode's note.

Files: `prompts.py`, `docs/prompt-failures.md`, and the tests that pin the old note.

**Checks.** The tests that read the note pin the new sentence. A request with one hidden image carries it once in that image's place. `make lint` and `make test` stay green.

**Blocked by.** 02
