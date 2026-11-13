# 11. Layer mcp: service and router

**Status.** done

## What to build

Move the code that acts and the routes of `mcp`. The session clients move as a folder.
- `mcp/service.py` to `mcp/service/mcp_service.py`
- `mcp/saved.py` to `mcp/service/saved_server_service.py`
- `mcp/_connection.py` to `mcp/service/_connection.py`
- `mcp/_result.py` to `mcp/service/_result.py`
- `mcp/client.py` to `mcp/service/client.py`
- `mcp/clients/` to `mcp/service/clients/`
- `mcp/tool.py` to `mcp/service/tool.py`
- `mcp/router.py` to `mcp/router/mcp_router.py`
- `mcp/schemas.py` to `mcp/router/schemas.py`
- `mcp/servers_router.py` to `mcp/router/server_router.py`
- `mcp/servers_schemas.py` to `mcp/router/server_schemas.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

10
