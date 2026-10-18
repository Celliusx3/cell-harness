# 01 · A group's member list is written again when a member leaves

**Status.** open

**What to build.** One test in `backend/tests/integration/test_web_groups.py`, on the code as it is: in the group Launch of Researcher and Writer, archive Writer, send a message, and the chat's last `group/members` event before the new `turn/start` names only Researcher.

**Checks.** The new test passes on the code as it is; the backend suite stays green. Break: make the member list never be logged again after the group is made; the new test fails.

**Blocked by.** none
