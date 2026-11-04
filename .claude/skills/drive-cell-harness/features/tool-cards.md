# Tool cards

Each tool call shows as a one-line card: its server in grey, then its name, such as "computer file list". A running call has a spinner and "running", and a finished one a check. A failed one has a warning and its error code, on a red card. Opening a card shows the arguments and the result.

A turn's cards, the text between them and its notes sit behind one line. While the turn works, the line names the step, "Running file list · 2 tools", or reads "Thinking · 2 tools" between steps. When the reply starts, it folds to "Used 2 tools", with "· 1 failed" when tools failed. A client tool's card (a question, a location, a key), an approval waiting for you and an app view stay outside it.

## Sub-features

- `execute_typescript` shows its program as code.
- An MCP App result has an "Open app" link.
- `run_subagent` holds one section per subagent, "## <name>" then its answer or "stopped: <reason>"; each subagent's own log is a file under `<sessions root>/../subagents/<call id>.<n>.jsonl`.

## How to get to it (user POV)

Ask something that needs a tool, for example "Compare Apple, Microsoft, Nvidia and Tesla on revenue growth over the last four years".

## Driving it with Playwright MCP

Wait for the header to read "Ready". Then `browser_snapshot`, and `browser_click` "Used N tools" to unfold the turn. `browser_click` the card's name button (for example "run subagent") and snapshot again to read its result.

## Gotchas

Whether the model chooses a tool is the model's decision; name the work plainly in the prompt, and retry once before calling it a failure. The line names the running tool, but a card shows no progress of its own while it runs. If you open the steps during a turn, they stay open after the reply starts.
