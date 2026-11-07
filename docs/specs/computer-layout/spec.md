# The computer server, laid out like the secrets package

## Problem

The `computer` server holds 22 files in one flat folder. The data types, the
two engines, the services that work the PC, and the startup check sit side by
side. A reader cannot tell from the folder which file is a model, which is an
implementation, and which is the logic. `backend/harness/secrets/` already
answers that question with folders, and the rest of the backend follows it.

## What changes for you

Nothing a person sees changes. Every tool, the Computer page and the PC behave
as before.

The code reads like `secrets/`:

```
computer/
  server.py, config.py, clock.py   the composition root and its settings
  models/      the data types, one subject per file
  engine.py    the Engine interface, as secrets/repository.py is
  engines/     docker.py and microsandbox.py, as secrets/repositories/disk.py is
  services/    the PC, its shell, browser, files, screen and Mac programs
  startup/     whether this machine can run a PC
  tools/       what the model calls, as before
```

A reader who wants the PC's lifecycle opens `services/machine.py`. A reader
who wants how microsandbox runs it opens `engines/microsandbox.py`. Each data
type sits in `models/`, in a file named for its subject.

## Decisions

1. **Move files, keep names.** A class or function keeps its name, so a search
   for it still works. Only the file and its folder change.
2. **One subject per model file.** `models.py` splits into the PC, the page,
   the files, the screen and the shell. `command.py` becomes the models for a
   command's result and an engine's errors.
3. **The interface stays at the top, its implementations go below.** This is
   how `secrets/repository.py` and `secrets/repositories/` are laid out.
4. **Only the `computer` server.** `backend/harness/` already follows this
   layout, and the other servers are small.

## Out of scope

- Renaming classes or functions.
- Any change in behaviour, and any bug found on the way. A bug is named in the
  reply and left for its own change.
- The other MCP servers.

## How we will know it works

1. The 568 tests that pass today pass after each ticket, with the same count.
2. Breaking one line in each moved piece makes a test fail.
3. The live app opens a page through a bot, and the Computer page takes
   control, as before.
