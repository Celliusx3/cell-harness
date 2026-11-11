# 01 Long-press, double-tap, more keys, and opening a link

**Status.** open

**What to build.** In `mcp-servers/phone/`: `long_press(x, y)` (a swipe in
place for 1 s), `double_tap(x, y)` (two taps 100 ms apart), `press_key` gains
`paste`, `tab`, `search`, `volume_up` and `volume_down`, and `open_url(url)`
(http and https only, through a VIEW intent). Each ends with a screenshot.

**Checks.** An integration test pins each Android command and refuses a URL
that is not http or https. On the real phone, a long-press in a note shows
Android's text menu in the tool's own screenshot, and `open_url` opens a
Pinduoduo link in the browser, which offers to open the app.

**Blocked by.** none
