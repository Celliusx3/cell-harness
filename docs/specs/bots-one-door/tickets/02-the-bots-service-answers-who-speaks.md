# 02 · The bots service answers who speaks

**Status.** done

**What to build.**
- `backend/harness/bots/service.py`: `BotService.first_speaker(session, text) -> Bot` looks up the chat's members, picks the first of `first_speakers(text, members.bots)`, raises `GroupEmpty(session.id)` when there is none, writes the speaker's instructions and, in a group, its member list into the session where they changed, and returns the speaker. `BotService.next_speaker(session) -> Bot | None` does the same with `next_speaker(session.events(), members.bots)` and returns `None` when nobody is next. `log_speaker` moves here from `runs/chain.py` as the private `_log_speaker(session, members, bot)`. `bot_instructions_event` and `group_members_event` become private and leave `backend/harness/bots/__init__.py`.
- `backend/harness/runs/service.py`: `start` and `hear` each call `self._bots.first_speaker(session, ...)` (the prompt, or the bot message's text); the `members_of_chat`, `first_speakers`, `GroupEmpty` and `log_speaker` uses go.
- `backend/harness/runs/chain.py`: `_next_turn` calls `bots.next_speaker(session)`; `log_speaker` goes; `discussion()` is renamed `discussion_events()` for the turn events it yields, and its one caller in `runs/service.py` follows.

**Checks.** The 126 turn-flow tests (`test_discussion.py`, `test_runs.py`, `test_runs_stop.py`, `test_bot_turns.py`, `test_bot_messages.py`, `test_gateway_groups.py`, `test_groups.py`, `test_layering.py`, `test_web_groups.py`, `test_web_bot_messages.py`, `test_web_bots.py`) plus ticket 01's, and the backend suite, pass before and after. Breaks: make `first_speaker` skip the instructions; `test_an_edit_is_logged_once_before_the_next_turn` fails. Make `next_speaker` always return `None`; `test_every_member_takes_a_turn_and_a_mention_brings_one_back` fails. Make `first_speaker` return a member when none is active; `test_a_group_with_no_active_member_starts_nothing` fails.

**Blocked by.** 01
