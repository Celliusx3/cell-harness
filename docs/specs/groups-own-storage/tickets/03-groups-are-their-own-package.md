# 03. Groups are their own package

**Status.** done

## What to build

Move everything about groups from `harness/bots/` to a new `harness/groups/`, in the same four layers.
`Group`, `GroupDraft`, `GroupsFile`, `ChatMembers`, `EmptyGroupError`, `GroupMemberNotFound` and the member limits go to `groups/domain/models.py`. `turn_order.py`, `group_repository.py`, `group_service.py` and `group_router.py` keep their names in the new package.
`harness/bots/` keeps the bots only, and imports nothing from `harness/groups/`.
Every importer, in `harness` and in the tests, reads the group names from `harness.groups`. `CLAUDE.md` lists `groups` among the features.
No behaviour changes, and no name changes but the package.

## Checks

`make lint` and `make test` are green before and after, with the same number of tests. `grep -rnE "Group|turn_order|ChatMembers" backend/harness/bots` finds nothing. `grep -rn "harness.groups" backend/harness/bots` finds nothing.

## Blocked by

02
