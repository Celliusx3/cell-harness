# 10. Layer mcp: domain and repository

**Status.** open

## What to build

Move the data, the pure rules and the storage of `mcp`. Delete the empty `models/` and `repositories/` folders.
- `mcp/models/commands.py` to `mcp/domain/commands.py`
- `mcp/models/errors.py` to `mcp/domain/errors.py`
- `mcp/models/returned_file.py` to `mcp/domain/returned_file.py`
- `mcp/models/saved.py` to `mcp/domain/saved.py`
- `mcp/models/server.py` to `mcp/domain/server.py`
- `mcp/models/status.py` to `mcp/domain/status.py`
- `mcp/csp.py` to `mcp/domain/csp.py`
- `mcp/keys.py` to `mcp/domain/keys.py`
- `mcp/repository.py` to `mcp/repository/saved_server_repository.py`
- `mcp/repositories/disk.py` to `mcp/repository/disk_saved_server_repository.py`

## Checks

- `make lint` passes, including the 300-line cap.
- `make test` passes with 2041 tests or more, coverage over 80%.
- `uv run python -c "import harness.web.server"` exits with no error.
- The layering test from ticket 01 passes for this package.

## Blocked by

01
