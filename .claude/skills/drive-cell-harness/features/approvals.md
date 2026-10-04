# Approvals

A call to a tool that writes (listed in `approval.tools`, or a server tool whose name has no read verb) stops the turn and shows a card under the call.

## Sub-features

- "Allow once", "Allow for this conversation", "Always allow", "Deny".
- The Approvals page lists the tools allowed always, and takes them back.

## How to get to it (user POV)

Ask the bot to save something, for example "remember that my favourite colour is green".

## Driving it with Playwright MCP

Send the prompt, `browser_wait_for` "Allow once", `browser_click` the choice, then wait for the turn to finish.

## Gotchas

"Always allow" writes the grants file; in this copy that is `$RUN/harness/approvals.json`, never the person's.
