# 01. A tool from an MCP server can wait for the person

**Status.** open

## What to build

A tool whose `_meta` declares that it waits for the person ends the turn as `pending`, as a client tool does. Read it in `harness/mcp/service/tool.py`.
The tool's result carries its card, and the harness keeps the call unanswered. The person's answer goes through `POST /api/conversations/{id}/calls/{call_id}/output` and opens the next turn. Typing skips it, as for `get_location`.

The rule names no tool. Read `docs/client-data.md` first: the pending path, `Runtime.resume` and `SKIPPED` already exist.

## Checks

An integration test with a fake MCP server whose tool declares the wait. Calling it ends the turn `pending`, and posting an output opens a turn whose first event is that call's result. A second test types a message instead, and the harness answers the call as skipped. Both fail before the change.

## Blocked by

none
