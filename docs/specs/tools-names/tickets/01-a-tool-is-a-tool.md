# 01 · A tool is a Tool, in the models folder

**Status.** open

**What to build.** `tools/definition.py` moves to `tools/models/tool.py`, and `ToolDefinition` becomes `Tool`, with `NAMESPACE_SEPARATOR` beside it. Every import and use follows. The MCP files that import the MCP library's `Tool` import it as `McpTool`. `ClientTools.definitions()` and `ClientToolService.definitions()` become `tools()`, and the catalog's `_definition` becomes `_tool_for`.

**Checks.** `make lint` and `make test` green (1489 passed). Every tool's schema byte-identical. `git grep -nwE "ToolDefinition|harness\.tools\.definition" -- backend` and a search for `.definitions()` find nothing.

**Blocked by.** none
