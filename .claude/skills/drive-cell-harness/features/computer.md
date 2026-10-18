# Computer

Every bot shares one Linux desktop with Chrome (Rakazo's image, a Docker container named `cell-harness-computer`). The bots use it through `computer__browser_navigate`, `computer__browser_read_page` and `computer__browser_act`, reading pages as text. The person uses it on the Computer page (the screen icon in the sidebar): a live screen streamed over VNC through the backend's `/api/relay`, so any device that can open the app can watch and control it.

## Sub-features

- Opening the page starts the computer if it is stopped ("Starting the computer…"), then takes control: the header reads "You have control until HH:MM" with a Release button. The hold lasts 15 minutes from Take control.
- After Release, or when the hold runs out, a banner reads "Watching only. Press Take control to use your keyboard and mouse."; the screen still updates but ignores input.
- While the person holds control, the bots' browser tools answer "The person has taken control of the computer's screen, so this did nothing…".
- Terminal (only while holding control) opens a login shell on the computer beside the screen; Release closes it.
- Files lists the computer's home folder, previews text and images, downloads; Upload only while holding control, 10 MiB a file.
- A `computer__browser_navigate` tool card has "Open app": a watch-only preview made of screenshots.
- `computer__shell` runs a command for a bot (it asks once per chat). The chat's files and the skills shipped with the app sit at their own Mac paths inside the computer, and a loaded shipped skill names its folder; a skill in the editable folder is not in the computer and names none. A skill can declare a Mac program in its `SKILL.md` metadata (`host-service`, `host-service-env`); the computer starts it and hands each command its address and token as `<NAME>_ADDR` and `<NAME>_TOKEN`, under the name the skill gives. A command still running after 15 seconds answers `running`; the same call again waits on.
- The page pings `keep_awake` every minute, so the 10-minute idle stop waits while it is open.

## How to get to it (user POV)

Click the screen icon in the sidebar, or go to `/computer`. Docker must be running. For the bots' side, ask a bot to look something up on a website; with `llm` on a small local model the bot may fail to call the tools.

## Driving it with Playwright MCP

`browser_navigate` to `/computer` and wait for "You have control until". The screen is an iframe titled "The computer's screen": click into it with `page.mouse.click` at coordinates inside its bounding box, then `page.keyboard.type`; check the result with `browser_take_screenshot`. Terminal input goes to `.xterm-helper-textarea`. Upload opens a file chooser: click Upload, then `browser_file_upload` with a path under the folder Claude Code was started in. Release when done, so the bots are not refused.

## Gotchas

The computer is one container for everyone: what you type, and the tabs and logins you leave, are the bots' too. The first page call on a freshly created computer sometimes takes more than 25 seconds and fails while Chrome starts. Watch-only ignores the keyboard by design: "I cannot type" is usually a page that is not holding control. A copy of the app started before this feature has no relay route; restart its backend. The computer can reach every port on this Mac through `host.docker.internal`, and the app has no login: a command run with `computer__shell` can call the app's API as the person.
