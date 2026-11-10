# Chat modes

Each chat is in Ask or Auto. Ask is the approvals rule: a protected call stops at a card. Auto runs every call with no card. A question such as `get_location` still waits in both.

## Sub-features

- A chip beside the attach button shows the mode's shield icon and "Ask" or "Auto". Below 640px wide it shows only the icon. Its tooltip describes the mode.
- Picking Auto opens "Switch to Auto?", a risk check with the box "I understand the risks and want to continue". "Enable Auto" stays disabled until the box is ticked. Picking Ask switches at once.
- Each switch is one line in the timeline, with the mode's icon: "Switched to Auto" or "Switched to Ask".
- Typing `/mode ask` or `/mode auto` switches the chat and starts no turn. `/mode` alone opens the chip's menu and sends nothing. A switch to the mode already on writes no line.
- A reload keeps the mode. A cleared chat goes back to the default, `approval.default_mode`.

## How to get to it (user POV)

Open a chat. The picker is in the message box. Ask the bot to save something to see a card in Ask, and none in Auto.

## Driving it with Playwright MCP

`browser_click` the picker, then the "Auto" item, then the checkbox, then "Enable Auto". `browser_wait_for` "Switched to Auto". Send a prompt that writes, and check that no "Allow once" appears.

## Gotchas

The picker shows only once the chat has loaded. A new-bot page has no chat yet, so it has no picker.
