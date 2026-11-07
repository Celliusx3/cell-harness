# MCP servers

Every MCP server the harness runs, on one page, in the order the person added them. A fresh harness has none. A change starts, restarts or stops only that server, with no restart of the harness.

## Sub-features

- Each row shows the server's name, its command line and its state: "Running", "Starting", "Waiting for a key: <names>", "Failed: <error>" or "Stopped". While one is starting the page asks again every 2 s.
- Each row lists the keys it needs, each "set" or "missing".
- On the Mac that runs the harness, the header has "Add server" and each server has Edit and Remove; a failed server also has Restart. Anywhere else the page is read-only and says "Change MCP servers on the Mac that runs the harness."
- "Add server" asks for Name, Command, Arguments (one per line, blank lines dropped), Settings (NAME and value rows) and "Keys it needs" (name and hidden value rows; a key is saved with the server, and an empty one on Edit keeps the saved key). Edit fixes the name.
- A setting with a value but no name is refused in the form. The harness's own refusals show under the field they are about (a bad name), or under the form (a name taken, a key also given as a setting).
- Remove asks first: "Remove <name>? Bots lose its tools."

## How to get to it (user POV)

Settings, then "MCP servers" under Credentials, or `/settings/mcp`.

## Driving it with Playwright MCP

Launch with `HARNESS_MCP__PATH="$RUN/harness/mcp.json"` too, so added servers never reach `~/.harness/mcp.json`. Wait for "Add server", click it, `browser_fill_form` the fields by label ("Name", "Command", "Arguments"; rows are "Setting 1 name", "Setting 1 value", "Key 1 name", "Key 1 value" after "Add setting" / "Add key"), then "Save". To add the PC, name it `computer` and type the `make dev` command in [mcp-servers/README.md](../../../../mcp-servers/README.md); without virtualization its row shows "Failed: …". Remove opens a confirm: `browser_handle_dialog` with `accept: true`. A save through the page server answers 403: `curl -s -o /dev/null -w '%{http_code}' -X POST localhost:4997/api/mcp/servers`.
