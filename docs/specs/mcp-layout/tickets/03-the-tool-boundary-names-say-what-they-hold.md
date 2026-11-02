# 03 — the tool boundary names say what they hold

## Status

open

## What to build

1. In harness/mcp/tool.py, rename the function that turns one published server
   tool into one model tool. It is named for the tool the caller gets back.
2. Rename its published-tool parameter to the word the service already uses for
   a server's own tool list.
3. One name for the name a server knows a tool by: the connection command
   field, the service call parameter and the client protocol parameter all take
   it. Touches harness/mcp/tool.py, harness/mcp/service.py,
   harness/mcp/connection.py, harness/mcp/client.py.
4. One name for the name the model calls a tool by: the outcome builder and the
   two returned readers take it.
5. The server id parameter is named for the id in every signature it appears
   in.
6. Update the keyword call sites in test_mcp_tool.py, test_mcp_images.py and
   test_tool_files.py.

## Checks

1. `cd backend && make test-unit` is green before and after.
2. `cd backend && make test-integration` is green before and after. The stdio
   run proves the client boundary still connects a real server.

## Blocked by

02
