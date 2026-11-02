# 02 — a result module beside the tool module

## Status

done

## What to build

1. Create harness/mcp/result.py, named for what a tool call returns.
2. Move into it what a tool result becomes for the model: the outcome builder,
   the content renderer, the returned-paths and returned-images readers, the
   meta file model, and their constant.
3. harness/mcp/tool.py keeps building and classifying tools. It imports the
   outcome builder from result.py. Its docstring now covers tools only.
4. Update the imports in test_mcp_tool.py, test_mcp_images.py and
   test_tool_files.py. Nothing else moves.

## Checks

1. `cd backend && make test-unit` is green before and after.
2. `make lint` is green after.

## Blocked by

none
