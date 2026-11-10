# 01 · Backend: one word for the approval mode, and no duplicates

**Status.** done

**What to build.** The backend renames and reshapes from the approved scan:

- `RunService.set_mode` and `ChannelGateway.set_mode` become `set_approval_mode`. `RunService.mode_of`, `ChannelGateway.mode_of` and `Toolset.mode_of` become `approval_mode`.
- `Runtime.approval_mode(session)` and `Runtime.approval_mode_switch(session)` hold the no-toolset case once. `RunService._mode_in` is deleted, and `MODE_WITHOUT_TOOLSET` moves to `runtime/service.py`.
- `Session.approval_mode_switch` becomes `approval_mode_switch_since_last_step`. `ModeSwitch` becomes `ApprovalModeSwitch`, and `_latest_mode` becomes `_latest_approval_mode`.
- `_start_step` becomes `_start_step_noting_mode_switch`. `_mode_line` becomes `_approval_mode_reminder`, and `MODE_LINES` becomes `APPROVAL_MODE_SENTENCES`.
- `ModeCommand(word)` becomes `ModeQuestion() | ModeChoice(mode) | UnknownModeWord(word)`. `mode_named` and `_MODE_OF_WORD` are deleted.
- `mode_is` becomes `mode_reply`, and `mode_words` becomes `mode_usage_reply`. `MODE_IS`, `MODE_WORDS` and `MODE_NAMES` become `MODE_REPLY`, `MODE_USAGE` and `MODE_LABELS`.
- `slash_words` becomes `command_words`, and `_mode_reply` becomes `_answer_mode_command`.
- In `routes.py`, `_switched` becomes `_switch_by_command`. A new `_chat_session(web, id)` replaces the duplicated "running turn's session, else load it" block.
- In tests, `_turn_ends` becomes `_turn_end_reasons`.

**Checks.** The 49 guarding tests pass before and after, and `make lint` and `make test` stay at 1790. Each moved piece is broken once on purpose and a test fails.

**Blocked by.** none
