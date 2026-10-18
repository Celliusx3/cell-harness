# 03 · One not-blank rule for a bot's and a group's form

**Status.** done

**What to build.** Only `backend/harness/bots/models.py`. One text type, `NonBlankText = Annotated[str, AfterValidator(...)]`, that strips the text and refuses an empty result with today's message, "must not be blank", as `SecretValue` names a key's value. `BotDraft.name`, `BotDraft.instructions` and `GroupDraft.name` use it, keeping their `Field` descriptions; both `_not_blank` validators go. `GroupDraft._once_each` becomes `_refuse_repeats`.

**Checks.** `test_groups.py`, `test_native_bots.py` (including ticket 01's schema test) and the backend suite pass before and after. Break: stop stripping; the test that saves " Launch " as "Launch" fails. Drop a description; ticket 01's schema test fails.

**Blocked by.** 01
