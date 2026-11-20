# 01 You can edit a group's name, members and lead

**Status.** done

**What to build.** `Group` gains `lead_id: str | None`. A new
`GroupEdit` (name, member_ids, lead_id) is saved through
`PATCH /api/groups/{id}`, with an `update` on the group repository and
the service. A group settings page at `/groups/{id}` edits the three,
and the group chat's header links to it. A lead that is not a member is
refused with a 422.

**Checks.** An integration test patches a group's name, members and
lead, then lists groups and sees the change. A lead outside the members
gets a 422. In the browser, renaming Market Desk shows the new name in
the sidebar.

**Blocked by.** none
