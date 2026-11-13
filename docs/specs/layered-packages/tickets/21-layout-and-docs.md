# 21. Describe the layered layout

**Status.** open

## What to build

Rewrite the Layout block in `CLAUDE.md` so every feature package reads as layered.
Grep `docs/`, `DESIGN.md`, `mcp-servers/README.md` and `CLAUDE.md` for every old module path, and update each one.
Delete any `__pycache__` folder left in a moved place.

## Checks

- `git grep` for each old module path returns nothing outside `docs/specs/layered-packages/`.
- `make lint` and `make test` pass.

## Blocked by

02, 03, 04, 05, 06, 07, 09, 11, 12, 14, 17, 20
