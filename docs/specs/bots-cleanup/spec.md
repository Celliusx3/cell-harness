# Bots cleanup

## Problem

The bots code works, but it is harder to read and easier to break than it needs to be. A bot's form is checked at the edge and then taken apart, so the code that saves bots would save a blank name. The entry that writes a bot's instructions into its chat is built in two places. The rule that a bot's chat has the bot's id is written in two places. One archive reads the bots file three times through four small helpers. Several names make the reader open the code to learn what they give back: a lookup called find that skips archived bots, a function called first_line that returns the bots who answer, two helpers called "once each" that do opposite things.

## What changes for you

Nothing a person sees changes. The same bots and groups are listed in the same order, the bots file holds the same data, and every chat logs the same events.

How the code reads after it:

1. A bot is made and edited from its whole checked form, the way a group already is, and one "not blank" text type serves both forms.
2. One builder makes the entry that writes a bot's instructions into its chat, beside the one that writes a group's members; each is named for the event it makes.
3. Finding who answers in a chat asks the one method that maps a bot to its chat.
4. Each call reads the bots file once and writes it once, through two helpers.
5. Every name in the bots folder says what it holds or gives back: the active-bot lookups say "active", a key's name is called a secret name, a bot id is called an id, and the code that picks who speaks next talks about speakers and a queue, not lines.

## Decisions

- Making a bot takes its form whole, as making a group already does.
- The "not blank" rule is a named text type, as a saved key's value already is.
- The bot-to-chat mapping stays a method on the bots service, the service that owns the relation.
- The deciding code stays as private methods handed the file already read; the strict option, module functions, would need the built-in bots and the mapping passed on every call.
- The error names stay as they are, named for the condition like the project's other errors.

## Out of scope

- A bot's own chat and a group chat as two separate types.
- Opening the built-in bots' chats when the server starts.
- The turn code's discussion function, and the find lookups of the skills and keys services.
- One shared helper for writing a file through a temp copy.
- The temp copy of the bots file left on disk when its rename fails. A bug, for its own change.

## How we will know it works

- The backend suite passes with the coverage gate, and lint passes, after every ticket.
- The 184 bot tests that passed before still pass, with only call shapes and names changed, plus two new ones: restoring Assistant leaves it as it was and writes nothing, and the bot_create tool's arguments are a name and instructions, each with its description.
- Each ticket's piece, broken on purpose, fails a test.
