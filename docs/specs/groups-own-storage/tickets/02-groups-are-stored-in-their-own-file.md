# 02. Groups are stored in their own file

**Status.** done

## What to build

Add `GroupRepository` in `harness/bots/repository/group_repository.py` with `groups()` and `add(group)`, over a `GroupsFile` model that holds the one list.
Add `GroupSettings` with `path` to `harness/config/sections.py` and `settings.py`, and `groups.path` to `backend/config.json` and `desktop/config.json`.
`GroupService` takes `(bots, sessions, groups, app_events)`. It saves through the repository and publishes `BotsChangedAppEvent`. `GroupRouter` takes the group service only.
Delete `groups` from `BotsFile`, `groups()` and `add_group()` from `BotRepository` and from `BotService`.
Groups saved in the bots file before this are ignored. Add no code to move them.
Add `HARNESS_GROUPS__PATH` to the launch block of `.claude/skills/drive-cell-harness/SKILL.md`.

## Checks

A test reads a bots file that still holds a `groups` list: its bots load, `GET /api/groups` lists nothing, and saving a bot writes the file without that list. A group made through `POST /api/groups` is in the groups file and not in the bots file. `tests/unit/test_group_repository.py` passes with no service. `grep -rnE "groups\(\)|add_group" harness/bots/service/bot_service.py harness/bots/repository/bot_repository.py` finds nothing. `make lint` and `make test` are green. A browser run on a new data folder makes a group, shows it in the sidebar, and its members answer in turn.

## Blocked by

01
