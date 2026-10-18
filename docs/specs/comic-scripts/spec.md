# The comic skill's scripts, one job per file

## Problem

The translate-comic skill tells the bot not to call a PhotoCraft tool that no longer exists, its write result carries a field the skill never explains, and four sentences that each fixed a model failure have no test. In the scripts, the write step runs the command, decides what to erase and checks spills; the PhotoCraft file is near the line cap with two subjects; a page travels under two names; and many functions and classes are named for something other than what they give back.

## What changes for you

1. The bot reads a shorter skill text: the line about PhotoCraft tools is gone.
2. A page's write result no longer lists the bubbles cleared whole; the bubble is still cleared, and the bot sees it in the pictures it checks.
3. Nothing else the bot or the person sees changes. The scripts read differently:
   - the write step reads, calls and writes, and the decisions sit in the lettering files;
   - talking to an open PhotoCraft page, lettering its text, and the lock each have a file;
   - the work folder takes a page's file name everywhere;
   - each function is named for what it gives back, each class for what it is.

## Decisions

- The field naming bubbles cleared whole is dropped, the person's choice on 2026-10-18.
- The work folder takes the page's file name and finds every path itself, as the chat files service takes a file name and finds its path.
- The helpers used after "with" keep their names (connected, opened, held), as Python's own closing and suppress read.
- The spill check gets its own file, as the left-over check has.
- The tuning numbers keep their short names, except the spill check's, which get full names when they move.

## Out of scope

- Ticket 09's clear-report clause: a small model's boxes miss bubbles.
- A computer per chat.
- Any change to how a page is erased, lettered or checked.

## How we will know it works

- The skill's own suite, 115 passed at 99% before, passes after, with one more test reading the skill text.
- The harness suite, 1428 passed before, passes after.
- Lint is clean on both, and every file is under 300 lines.
- The five Japanese pages, attached in the chat with Gemini, come back as an English archive, with PhotoCraft up on the Mac.
