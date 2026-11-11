# Phone

Every bot shares one Android phone (Redroid 13, no Google Play) in a microsandbox microVM on a kernel of our own with binder, from the `phone` MCP server. The bots use it through `phone__screenshot`, `phone__install_app`, `phone__open_app`, `phone__tap`, `phone__swipe`, `phone__type_text` and `phone__press_key`, each answering with a new screenshot; the `use-the-phone` skill tells them how. The person watches it and takes control on the Computer page, through droidVNC-NG inside Android and the same noVNC relay as the PC.

## Sub-features

- The first phone call starts the phone (about 8 s from stopped, longer the first time it is made) and waits for Android; later calls take under a second.
- `phone__install_app` takes the full path of an APK attached to the chat and answers "Installed <package>."; a file outside the chat's files is refused.
- `phone__type_text` types ASCII only; other text is refused in words.
- The phone reaches the public internet only, never the Mac or the person's network.
- After 10 minutes with no phone call (`PHONE_IDLE_MINUTES`), the phone stops; its apps and their data stay on its own disk.
- On the Computer page, the "Phone" panel beside the PC's screen opens watching: "Watching only. Press Take control to use your keyboard and mouse." "Take control" makes it "You have control until HH:MM" with "Release", for 15 minutes; a bot's phone call meanwhile answers "A person has the phone: …". Leaving the page and coming back while you hold it shows your hold again, with Release.
- Without a `phone` server the panel reads "The phone is not set up."; with one that is not connected, "The phone is not available right now."

## How to get to it (user POV)

Add a server named `phone` on MCP servers ([mcp-servers.md](mcp-servers.md)) with the command and settings in [mcp-servers/README.md](../../../../mcp-servers/README.md): `PHONE_IMAGE`, `PHONE_KERNEL` and `PHONE_KERNEL_SHA256` name the image and kernel, `PHONE_FILES_DIR` the chat files. Then ask a bot to take a screenshot of the phone, or attach an APK and ask it to install and open it. Open "Computer" to watch.

## Driving it with Playwright MCP

The bots' side needs a model that sees images: give Assistant one on the copy's Credentials page. Put the copy in Auto mode ("Mode: Ask", then "Auto", then "Switch to Auto") so each tap does not wait on an approval card. For the person's side, `browser_navigate` to `/computer`. The panel is an `<aside>`: find it with `page.getByRole('complementary').filter({ has: page.getByRole('heading', { name: 'Phone' }) })`, not a CSS `[role=complementary]`, which misses an implicit role. Its screen is an iframe: click into its canvas with `page.mouse.click` at a point scaled from the phone's 720x1280 pixels, as for the PC. Release when done, so the bots are not refused.

## Gotchas

Apple Silicon only. `MSB_HOME` must be short: microsandbox refuses a socket path of 104 bytes or more. A kernel that does not hash to `PHONE_KERNEL_SHA256` stops the server at start, naming both digests. An app that needs a Google account or Play services may refuse to run. The phone is one for every bot: logins and apps left on it are every bot's.
