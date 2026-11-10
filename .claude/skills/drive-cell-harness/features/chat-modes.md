# Chat modes

Each chat is in Ask or Auto. Ask is the approvals rule: a protected call stops at a card. Auto runs every call with no card. A question such as `get_location` still waits in both.

## Sub-features

- A picker beside the attach button in the message box shows "Ask" or "Auto".
- Picking Auto opens a dialog, "Let this bot act without asking in this chat?", with "Cancel" and "Switch to Auto". Picking Ask switches at once.
- Each switch is one line in the timeline, with the mode's icon: "Switched to Auto" or "Switched to Ask". Auto shows in the accent colour, in the line and in the picker.
- Typing `/mode ask` or `/mode auto` switches the chat and starts no turn. `/mode` alone shows "Use /mode ask or /mode auto. Mode: Ask." in the red strip above the box.
- A reload keeps the mode. A cleared chat goes back to the default, `approval.default_mode`.

## How to get to it (user POV)

Open a chat. The picker is in the message box. Ask the bot to save something to see a card in Ask, and none in Auto.

## Driving it with Playwright MCP

`browser_click` the picker, then the "Auto" item, then "Switch to Auto". `browser_wait_for` "Switched to Auto". Send a prompt that writes, and check that no "Allow once" appears.

## Gotchas

The picker shows only once the chat has loaded. A new-bot page has no chat yet, so it has no picker.
