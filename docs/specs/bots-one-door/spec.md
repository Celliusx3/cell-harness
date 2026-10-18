# Bots answer who speaks, through one door

## Problem

To follow how a group chat picks who speaks, a reader opens four files in two packages. The run code asks the bots service who is in the chat, then calls the turn-order logic itself, then writes the speaker's instructions into the chat with a helper of its own, and after each reply does the same again. The turn-order file is open to any package, so nothing says the bots service is the way in, and its name, discussion, does not say what it decides.

## What changes for you

Nothing a person sees changes. The same bot answers first, the same bots follow, and every chat logs the same events in the same order.

How the code reads after it, with one example: you send "@Writer draft it" in the group Launch.

1. The run code asks the bots service one thing: who speaks first for this message. It gets Writer back, and starts Writer's turn.
2. Inside the bots service, in one place, read top to bottom: look up Launch's members, pick who answers from the mentions, write Writer's instructions and Launch's member list into the chat where they changed, and give Writer back. Nobody left to answer is refused there too.
3. After Writer's reply, the run code asks the bots service who speaks next, and gets a bot or nobody.
4. A bot message to Writer's own chat asks the same first question, so it is answered the same way.
5. The logic that decides the order sits in a file marked private to the bots package, named for what it decides, and a test stops any other package from importing a package's private file.

## Decisions

- The bots service is the only way in: the run code no longer calls the turn-order logic or writes a bot's instructions itself.
- A private file is marked with a leading underscore, the Python convention; AutoGen keeps its group-chat managers the same way, under a private folder with only the team classes exported.
- A bot message is answered through the same first-speaker question as a person's message. In a bot's own chat there is one member, so the answer is that bot, as today.
- The two questions are named for the bot they give back; each also writes that bot's instructions into the chat, which its one-line description says. To decide at approval: the strict reading of the naming rule would put that in the name.

## Out of scope

- A bot's own chat and a group chat as two separate types.
- The turn-order logic itself: mentions, the queue and the cap stay exactly as they are.
- The run loop's file name.

## How we will know it works

- The 126 tests that guard the turn flow pass before and after, with one new test first: when a group member is archived, the next message writes the new member list into the chat before its turn.
- A new layering test fails if any package imports another package's private file.
- The backend suite passes with the coverage gate, and lint passes, after every ticket.
- Each ticket's piece, broken on purpose, fails a test.
