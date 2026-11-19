# 02 A group answers by its reply setting: Everyone, Lead or Mentions

**Status.** open

**What to build.** `Group` gains `reply: Literal["everyone", "lead",
"mentions"]`, `everyone` by default, so older groups files still load.
`SpeakerQueue.after_message` takes the group's reply setting and lead.
A message with @names still goes to those bots. Without one, Everyone
queues every member, Lead the lead, else the first member, and Mentions
nobody. The settings page gains the choice.

**Checks.** Unit tests on `SpeakerQueue` cover the three settings, with
and without @names. In the browser, a Market Desk set to Lead with
Judge as lead answers a plain message with Judge only.

**Blocked by.** 01
