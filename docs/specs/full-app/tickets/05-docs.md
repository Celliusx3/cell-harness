# 05 The docs describe one full app

**Status.** open

**What to build.** `docs/specs/desktop-app/spec.md` says this spec replaces
its scope limits. The Makefile help, the desktop README and PHASES.md
describe the full app: what it carries, its size, its data folder and its
own PC, and how capability keys are added.

**Checks.** `make lint` and `make test` are green. A search of the docs for
"chat and skills only" finds nothing about the current app.

**Blocked by.** 03, 04
