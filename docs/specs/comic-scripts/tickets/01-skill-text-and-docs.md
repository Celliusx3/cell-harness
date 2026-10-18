# 01 The skill text, the write result and the docs

**Status.** done

**What to build.** A test, `scripts/comic/tests/unit/test_skill_text.py`, reads `SKILL.md` and asserts the four sentences the ledger rows rely on (steps 2.2, 2.3, 2.4). Remove "Do not call any `photocraft__` tool." from `SKILL.md`. Drop `whole_bubble` from `WriteResult`, `Erasure` and `LetterLines` (`letter_lines` then returns its boxes), keeping the whole-bubble erase itself. Delete `Outcome.lettered`, which nothing reads. `is_whole_image` catches `OSError` without its subclass `FileNotFoundError`. `CLAUDE.md`, `PHASES.md` insertion 19 and comic-skill ticket 06 say only the skills shipped with the app sit in the computer; comic-skill ticket 10 notes the dropped field.

**Checks.** `make test-skills` passes with nine more tests (124); shortening an asserted sentence in `SKILL.md`, or adding a result field the skill does not name, turns it red. `make test`, `make lint`, `make lint-skills` green.

**Blocked by.** none
