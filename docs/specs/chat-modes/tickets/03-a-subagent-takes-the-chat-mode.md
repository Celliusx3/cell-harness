# 03 · A subagent takes the chat's mode when it starts

**Status.** done

**What to build.** The subagent tool passes the calling origin's `mode` to `Subagents.__call__`. That writes an `ApprovalModeChanged` event with the mode into the subagent's new session before its turn starts. So a subagent started in auto runs protected calls, and one started in ask stops with today's reason. Files: `runtime/subagents.py`, `tools/native/subagent/tool.py`.

**Checks.** An integration test: a subagent started from an auto chat runs a protected fake tool. One started from an ask chat returns the "needs the user" stop. `make lint` and `make test` stay green.

**Blocked by.** 01
