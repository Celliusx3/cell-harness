# 01 · The chat's mode is saved, and the bot's calls follow it

**Status.** done

**What to build.** A new session event `ApprovalModeChanged`, typed `approval/mode`, with `mode: ApprovalMode`, where `ApprovalMode = Literal["ask", "auto"]`, in `session/models.py`. `Session.approval_mode(default)` in `session/log.py` gives the mode of the latest such event, or `default`. `ApprovalSettings` gains `default_mode: ApprovalMode`, and `backend/config.json` sets it to `"ask"` explicitly.

`CallOrigin` gains `mode: ApprovalMode`. `runtime/tool_run.py` builds it from the session and the default. `ToolService.dispatch` returns `Pending` only when the origin's mode is `ask`. A script's calls carry the same origin, so they follow the mode too.

`RunService.set_mode(conversation_id, mode)` appends the event to the running turn's session, or to the stored session when no turn runs. A route `PUT /api/conversations/{id}/mode` with body `{"mode": "ask" | "auto"}` calls it. A body with any other mode is a 422.

**Checks.** An integration test with a protected fake tool: in a new chat a call to it is pending. After `PUT …/mode` with `auto`, the next call runs with no card, and a script's call to it runs too. After `PUT …/mode` with `ask`, it is pending again. A unit test shows that the latest event wins and that a chat with none uses the default. `make lint` and `make test` stay green.

**Blocked by.** none
