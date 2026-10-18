# Computer shell

## Problem

The bots' computer runs a skill's scripts, and one skill's scripts need a program that runs only on the Mac. The computer server, which is meant for every skill, knows that one program by name: it reads a setting that names it, starts its server, and hands every command its address, its token and a lock file. A second skill that needs a Mac program would mean new code in the computer server, the lock belongs to the skill, and removing the skill leaves the program started for nobody. The file that keeps the computer running is also near the line cap, and several names need their docstring to be read.

## What changes for you

Nothing you see changes: the comic skill's pages are erased and lettered as before, and without the Mac program installed the computer runs as before.

How the code reads after it:

1. A skill's instructions file names the Mac program it needs, the command that starts it, and the name its address and token go under.
2. At startup the computer server reads the skill folders it mounts, starts each program a skill names that is installed, and hands commands its address and token. It names no skill and no program in its code.
3. The skill keeps its own lock.
4. The shared-folder rules live in their own file, and names say what comes back.

## Decisions

- The declaration lives in the skill's metadata, the free-form field of the skills format; OpenClaw's skills declare required programs and Codex's the servers they need.
- Only the skill folders the computer mounts, the repo's own and read-only, are read for declarations. A declared program runs on the Mac.
- A program that is missing, or a declaration that does not parse, is logged and skipped; the computer still starts.

## Out of scope

- A computer per chat; every bot's commands see every chat's files, and two identical commands at once share one job.
- The token on the docker command line.

## How we will know it works

- The computer server's suite passes before and after: 451 passed and 14 skipped today; the harness's 1418.
- A declared program is started, its address and token reach a command, and it is stopped with the server; one that is missing or malformed is skipped with a log line.
- A skill outside the mounted folders is never read for a declaration.
- One live run with the real Mac program declared by a skill in a scratch folder.
