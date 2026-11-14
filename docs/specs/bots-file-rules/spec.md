# The bots file's rules, and two leftovers

## Problem

The bots service is hard to read. Every method reads the whole bots file, works out the new list of bots inside the service, and writes the whole file. The list rewriting cannot be tested without a service.

Two leftovers sit beside that. Asking for the list of bots also creates the built-in bots' chats. An edit of a bot may leave the worker limit out, and then the saved number is kept.

## What changes for you

Nothing you see changes. These steps show the two leftovers going away.

1. You open the app on a new install. The sidebar lists Assistant.
2. You open Assistant's chat. It is empty, as it is today.
3. You type "hi". Assistant's chat is saved now, with its instructions first, and Assistant answers.
4. A schedule that is due in Assistant's chat before you ever typed there still runs.
5. A bot that messages Bot builder before you ever opened its chat still reaches it.
6. You press **New**, then **Bot**, and describe a bot. Bot builder's chat is saved now, and it answers.
7. You edit a bot and save. The form sends the worker limit, as it does today.
8. You finish the setup screen. It sends Assistant's worker limit with the model you chose.

After the change the code reads this way. The bots file's type is plain data: its bots and its groups. The bots repository fetches one stored bot, adds one, updates one or several, and deletes one. It does the same for groups. Each service method asks the repository for a bot, makes a changed copy, and hands the copy back. The service never handles the whole list. The service works out which bots are active, because only it knows the built-in bots.

## Decisions

- A chat is created when the first message is heard in it, for a person, a schedule or another bot alike. The channels already do this for a person's message.
- A schedule or a bot message for a bot that still exists never ends because its chat was not written yet. Today both treat that as "the bot is gone".
- An edit always carries the worker limit. The setup screen sends an edit without it today, so it gains that one value. To decide at approval.
- The turn order stays an interface with one implementation. Issue #90 plans a second one, a group lead.
- Group storage stays in the bots service. Moving it adds two arguments at 31 places that build the group service.
- The three ways to set a bot's keys stay. Folding two of them changes the order of a bot's keys.
- Archive and restore, groups, and Bot builder all stay, as the person chose.
- The guess for chat logs that name no bot stays, because such logs are on disk.
- Restoring a built-in bot keeps doing nothing.

## Out of scope

- Any change to what a group does, or to who speaks next.
- Splitting the group service.
- Versioned files, webhooks, or any open issue.

## How we will know it works

- The 114 tests of the bots package pass before and after each part. Measured on 2026-11-14.
- New tests give the bots repository a file in a temporary folder and check the bots it stores, with no service. Tests of the bots service check which bots are active.
- On a new data folder, listing the bots leaves no chat saved.
- On a new data folder, a schedule due in Assistant's chat runs a turn and stays active.
- On a new data folder, a message from one bot to Bot builder is answered.
- In the browser, Assistant's chat opens empty on a new data folder, and "hi" gets an answer.
- An edit without the worker limit is refused. The setup screen still saves Assistant's model.
