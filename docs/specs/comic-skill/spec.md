# A comic translated by a skill and the bots' computer

## Problem

The person wants comic translation to be a skill that ships its own scripts, the way a Claude Code skill does, not a dedicated server. Today a bot cannot run a program anywhere: its computer offers only page tools, a chat's files never reach it, and nothing shows the model an image file. So the pixel work lived in a server of its own.

## What changes for you

1. You attach a comic (`.cbz`, `.zip` or one image) and say "translate this to English".
2. The bot loads the translate-comic skill. It asks once to run commands in its computer; you allow it for the chat.
3. It unpacks the comic in its computer and looks at each page, part by part.
4. For each page it sends the bubbles it found (where, what they say, the English). A script erases the original text with PhotoCraft and writes the English, then reports any line cut off, any spill out of a bubble, and any text still left.
5. It looks at the English page, fixes what the report and its own eyes found, and stops when the report is clear or after the third try.
6. It sends you the English archive and clears its working files, keeping only the archive.

## Decisions

- Commands run in the bots' shared Docker computer, through one shell tool, as Rakazo's bots run theirs inside the bot's computer.
- A chat's files and the skill folders appear in the computer at the same paths as on the Mac (files read-write, skills read-only), so a path the bot is told works in both places, as Rakazo keeps one workspace path per bot.
- A command still running after about 15 seconds answers "running" with how long it has run and its latest output; the same call again waits on. The old comic server answered "still working" the same way, and Rakazo streams a running command's output.
- Commands run detached and survive a dropped connection: measured, a killed client leaves its command running.
- The bubbles go to the script on the command's input, never inside the command line, because an apostrophe in English breaks quoting.
- Scripts reach PhotoCraft on the Mac through PhotoCraft's own headless server, with its token and its folder limits. PhotoCraft runs only on the Mac; measured, the computer reaches it and opens files in the shared folders.
- One script at a time works inside PhotoCraft: measured, two clients share one session, and one closing a page moves the other's page number.
- The model sees a page through a native "view image" tool, as Claude Code reads an image file.
- The page reading, box tightening, PhotoCraft erasing and lettering, and the three checks are the stashed comic server's, moved into the skill's scripts.
- Last: a box that points into a closed bubble holding no other item's box erases and letters the whole bubble, so a model that boxes roughly still clears it.

## Out of scope

- A computer per chat: every bot's commands see every chat's files, because the computer is shared.
- Making a small local model finish all its steps.
- Moving other servers' work into skills.
- Commands that run on the Mac itself.
- A login for the app: built, then removed on 2026-10-17 at the person's request (the app is reached over Tailscale). Measured, the computer reaches a service listening only on the Mac's own address, so a bot allowed to run commands can call the app's API as the person.

## How we will know it works

- Attach the five Japanese pages and ask for English with a capable model: you get five English pages back in an archive, the report says nothing is cut off, spilled or left, and the chat's working folder holds only the archive.
- Attach the Malay page whose box a small model placed 125 px off: no Malay is left.
- Every test suite passes, including the skill's own.
