# 08 The docs and the browser skill match the new chat

**Status:** done

**What to build.**

- `PHASES.md`: the line that records "Done · N tools" as the folded turn now records "Used N tools". It says the steps fold when the reply starts, and points to this spec.
- `.claude/skills/drive-cell-harness/SKILL.md`: the Drive steps say "Thinking", "Running … · N tools" and "Used N tools". The handles list "More", "Compact" and "Clear chat" in place of "Clear", and "Edit bot" as the pencil's label.
- `.claude/skills/drive-cell-harness/features/tool-cards.md` matches the new lines.
- `.claude/skills/drive-cell-harness/features/chat-progress.md` is new. It says what a person sees from send to the end of a turn, and how to check each step. `features/README.md` lists it.

**Checks.**

- `make lint` passes.
- By hand: follow the skill's Drive steps word for word on the built app. Every label it names is on the screen.

**Blocked by.** 01, 02, 03, 04, 05, 06, 07
