# Tool cards

Each tool call shows as a one-line card with the tool's name and "running…", "done" or an error code. Opening it shows the arguments and the result.

## Sub-features

- `execute_typescript` shows its program as code.
- An MCP App result has an "Open app" link.
- `run_subagent` holds one section per subagent, "## <name>" then its answer or "stopped: <reason>"; each subagent's own log is a file under `<sessions root>/../subagents/<call id>.<n>.jsonl`.

## How to get to it (user POV)

Ask something that needs a tool, for example "Compare Apple, Microsoft, Nvidia and Tesla on revenue growth over the last four years".

## Driving it with Playwright MCP

After the turn ends, `browser_snapshot`, then `browser_click` the card's name button (for example `run_subagent`) and snapshot again to read its result.

## Gotchas

Whether the model chooses a tool is the model's decision; name the work plainly in the prompt, and retry once before calling it a failure. Live progress inside a card is not shown anywhere yet.
