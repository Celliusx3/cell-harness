# File tools

## Problem

A bot's file tools could open, unpack and pack another chat's files, because a tool call was never told which conversation it ran in; that is fixed in this change, with a test per tool. What is left is hard to read: the four tools are split over three modules that mix tool definitions with the archive and image logic, unlike the sibling tool packages that keep definitions together and their argument models beside them. Startup builds the chat file service twice, once for the web channel and once inside the runtime. Several names need their docstring to be understood: a number padder named like a past participle, a yes-or-no named like a state, helpers that do not say what they return.

## What changes for you

Nothing you see changes beyond the fix: the same tools, the same descriptions, the same refusals.

How the code reads after it:

1. One chat file service, built at startup, used by the web channel, the turn loop and every file tool.
2. The file tool package keeps its tool definitions in one module and their argument models in another, like the sibling tool packages; the archive and image modules hold only what the tools do.
3. Names say what comes back or what they decide.

## Decisions

- The package layout follows the sibling tool packages that keep definitions and argument models apart.
- The startup service is passed into the runtime, as the image service already is.

## Out of scope

- A subagent's tool calls carry the subagent's own conversation; no file tool reaches a subagent today.
- The chat file service names its conversation parameter `chat_id` though it receives conversation ids; that is the chat files change's to rename.

## How we will know it works

- The whole backend suite passes before and after: 1417 today, with the three tests that a file tool refuses another chat's file.
- The frontend typecheck stays clean.
- Breaking one line in each moved piece turns a test red: startup handing the runtime a second service, a tool skipping the chat check, and the archive and image logic each losing one rule.
