# Group modes

## Problem

A group answers every plain message with every member, in order. Bots
hand over to each other with @mentions for up to six turns, and a bot
that forgets its @line ends the discussion. The person cannot pick who
answers or change a group after making it. They also cannot ask a team
to work toward a goal until it is done.

## What changes for you

Normal mode:

1. You open a group and click its name. A settings page shows the name,
   the members, the lead and the reply setting.
2. You change any of them and save. The group answers by the new
   settings from the next message.
3. The reply setting is one of Everyone, Lead, Mentions or Auto.
   Everyone answers with every member in turn, as today. Lead answers
   with the lead only. Mentions answers only when you @name a bot.
4. With Auto, you also pick a model. For each message that names no
   bot, that model picks one member, or every member. When it is less
   than 60% sure, the lead answers.
5. A reply that Auto picked shows a small line under it, such as
   "Picked by Auto · 94%".
6. A bot that writes @Bull brings Bull in once. Bull's own @names bring
   in nobody.

Goal mode:

7. In a group, you type `/goal decide what to buy on my watchlist today`
   and send it.
8. The lead answers first. It writes a short update, and it hands the
   next step to one member with a task.
9. That member answers. If it sends a worker, the run waits for the
   worker's report.
10. The lead and the members take turns, up to 13 turns in all. The lead
    always has the last turn.
11. The lead ends the run when the goal is done, when it needs you, or
    when it is blocked.
12. A card shows the goal, the lead and the turns used. It also shows
    how the run ended: done, needs you, blocked, limit reached or stopped.
13. Stop ends the run at once, and the card says stopped.

## Decisions

- **Two modes, chosen per message.** A plain message is normal mode,
  and `/goal` starts goal mode. OpenMausBot does the same, and Claude
  Code starts its goal loop with `/goal` too. Agno offers a route mode
  and a task loop led by a leader.
- **Reply settings.** Everyone, Lead, Mentions and Auto, from
  OpenMausBot. GolemBot has the same kind of setting per group
  (mention-only, smart, always).
- **Auto.** One short call to the model picked on the group, which
  returns one member or every member, with its confidence. At 0.6 or
  more the pick answers, otherwise the lead does. OpenMausBot does the
  same with its own small decision model. AutoGen, CrewAI, LangGraph
  and Agno use no confidence at all, so this rests on one source. A
  general model reports its own confidence, so 60% here is less exact.
- **One step of @mention hand-over.** From OpenMausBot. It replaces six,
  because goal mode carries the long discussions.
- **The lead.** An @name in the `/goal` text, else the group's lead,
  else the first member, from OpenMausBot.
- **The lead's choice is hidden.** The lead ends each turn with a block
  that names the next member and task, or the end and why. The chat
  never shows it. OpenMausBot hides its block in the same way, and
  AutoGen's selector and LobeHub's supervisor also name the next
  speaker from a model's answer.
- **A missing or broken block ends the run as blocked.** OpenMausBot
  treats it as a safe pause, never as a guess.
- **13 turns, lead last.** From OpenMausBot. AutoGen stops at 25
  messages, and GolemBot at 10 bot replies. One debate paper found
  that forcing more rounds made results worse, so the lead may end
  early.
- **Waiting for workers.** A member's turn ends when its workers'
  reports arrive. A member that stays busy past a time limit
  makes the lead's next turn carry a note, so the lead can pick someone
  else. Three such waits end the run as blocked. OpenMausBot waits on a
  busy member in the same way.
- **The same task three times ends the run as blocked.** From
  OpenMausBot.

## Out of scope

- Telegram and Discord. Groups exist only in the browser.
- A goal run started by a schedule.
- Resuming a stopped or blocked run. You send `/goal` again.
- A spending cap per run.
- Suggestions for `/goal` as you type.

## How we will know it works

- You change a group's lead and reply setting to Lead, then send a
  plain message. Only the lead answers.
- With Mentions, a message with no @name gets no answer, and one with
  @Bull gets Bull's answer.
- With Auto, a message about prices goes to Market Watcher, and the
  reply shows "Picked by Auto" with a percentage.
- A bot's reply that names two bots brings each in once, and their
  replies bring in nobody.
- `/goal` in Market Desk runs Judge, Market Watcher, Judge, Bull, Judge,
  Bear and so on. It ends with a card that says done and the turns
  used.
- While Market Watcher's worker runs, no other bot speaks until Market
  Watcher posts the report.
- Stop during a goal run ends it, and the card says stopped.
- No reply in the chat shows the lead's hidden block.
