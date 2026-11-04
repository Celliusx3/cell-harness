# Settings

Settings is its own screen. Its menu takes the chat sidebar's place and holds Credentials, Approvals and Skills under "Back to chats".

## Sub-features

- `/settings` opens Credentials. The menu marks the page that is open.
- "Back to chats" opens the chat page this tab showed before Settings. With nothing saved, it opens Assistant's chat.
- The old addresses `/credentials`, `/approvals` and `/skills` lead to their Settings pages.
- Before a model key is saved, every Settings page sends you to `/setup`, as every chat page does.

## How to get to it (user POV)

Click "Settings" at the sidebar's foot. In the Mac app, the menu-bar icon's "Credentials…" opens Credentials inside Settings.

## Driving it with Playwright MCP

`browser_click` "Settings", then "Credentials", "Approvals" or "Skills" in the menu. The open one has the `bg-accent-soft` class. `browser_click` "Back to chats" and check the URL is the chat you left.

## Gotchas

The way back lives in the tab's `sessionStorage` under `harness:chat-path`, so a new tab goes back to Assistant's chat. A saved path that is not a page of this app outside Settings counts as nothing saved.
