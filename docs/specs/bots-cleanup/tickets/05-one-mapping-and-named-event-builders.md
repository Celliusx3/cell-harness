# 05 · One mapping from a bot to its chat, and event builders named for their events

**Status.** open

**What to build.** In `backend/harness/bots/service.py`, `members_of_chat` finds a bot's own chat by asking `self.chat_of(bot.id) == chat_id` instead of comparing ids; `chat_of` stays the one method that maps a bot to its chat. `roster(group, members)` becomes `group_members_event(group, members)`, and a new `bot_instructions_event(bot) -> BotInstructionsEvent` beside it replaces the two places that build that event: `BotService._log_instructions` and `log_speaker` in `backend/harness/runs/chain.py`. Both are exported from `backend/harness/bots/__init__.py`.

**Checks.** `test_bot_service.py`, `test_groups.py`, `test_bot_turns.py`, `test_runs.py` and the backend suite pass before and after. Break: make `chat_of` return a different id; `test_a_chat_belongs_to_the_bot_whose_chat_it_is` fails. Make `bot_instructions_event` leave out the bot's id; `test_listing_opens_assistant_s_chat_only_the_first_time` fails.

**Blocked by.** 02
