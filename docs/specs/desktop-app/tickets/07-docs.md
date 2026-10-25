# 07 Docs

**Status:** open

**What to build.** `README.md` gains a Desktop app section: build it, install it, Open Anyway, and where the settings file is. `CLAUDE.md` gains a Layout line for `desktop/` and a run line for `make app`. `PHASES.md` status gains one line. `scripts/check-file-lengths.sh` also checks `desktop/src`, and the `Makefile` gains `test-desktop`.

**Checks.** `make lint` passes and checks `desktop/src`. `make test-desktop` passes. Every path the README names exists.

**Blocked by.** 05
