# A Credentials page

## Problem

Today the harness's keys and tokens live in a JSON file. A friend with the Mac app must find that file and edit JSON by hand. Then they must quit and reopen the app before a Telegram token works.

## What changes for you

1. You click the lock icon in the chat's sidebar. The Credentials page opens.
2. It lists the harness's own keys: the model's API key, the Telegram token and the Discord token.
3. A saved key shows as "saved, ends in …a1b2", never in full. An unset one shows "not set".
4. You paste a Telegram token and click Save.
5. If a bot is writing a reply, the page asks "A reply will stop. Save and restart?". You click Save and restart.
6. The harness restarts. After a few seconds the page says the change is applied, and the Telegram bot answers.
7. You click Remove beside the Telegram token and save. Telegram stops after the restart.
8. On your phone, the same page shows which keys are saved, masked. Save is not offered there.
9. In the Mac app, the menu-bar icon has "Credentials…", which opens this page in the app window.

## Decisions

- The page lists every setting marked as a secret that a person sets, so a key added later appears with no page change. OpenClaw marks sensitive fields in its schema the same way, and Assistant marks them write-only.
- A test fails when a text setting named like a key or token is not marked secret.
- A saved key is never sent to the page; only its last four characters are. An empty field keeps the saved key, and Remove clears it. Hermes refuses to save a masked preview back, and OpenMausBot shows "Configured" with Clear.
- The encryption key for saved keys is not listed. Nobody types it, and changing it makes every saved key unreadable.
- A key given by an environment variable shows read-only, with a note that the variable sets it. OpenMausBot notes that a key set in the environment hides a newly saved one.
- Save goes straight to the harness's own port, not through the page server. That port listens on this Mac only, so another device cannot reach it. The page server forwards requests without the browser's address, so it cannot tell this Mac from another device.
- The harness refuses a save that came through any proxy or from an address that is not this Mac. It also refuses a save from a page that is not one of its own. OpenMausBot refuses proxied requests in the same way.
- Save writes the per-machine settings file and keeps every value it does not change. The write replaces the file in one step, readable by its owner only, as the Mac app's setup window does.
- A save is checked against the whole settings model before it is written. A refused value is shown with the harness's message, and the key typed is never echoed back.
- A change to the settings file restarts the harness. `make dev`'s reloader watches the file, and the Mac app watches it too. anibridge restarts after a save, and its page waits for the server to return.
- If a reply is running, Save first asks, then restarts. To decide at approval: the strict reading is to refuse while busy, but you chose to ask.
- The page is named Credentials and holds the harness's own keys. The Keys page stays the keyring of keys the bots use.

## Out of scope

- Every setting that is not a key: the model name, the endpoint, timeouts, and the public URL. They stay in the file.
- A server's keys, such as the places server's Google Maps key. They come with connecting servers by URL.
- The bots' keys on the Keys page, and the bots and approvals.
- A login. The page is read-only off this Mac instead.
- Checking a token with its service before saving it.

## How we will know it works

- Open the Credentials page in `make dev`. The API key and both bot tokens show, each by its last four characters or "not set".
- Save a new Telegram token. The harness restarts, and the Telegram channel starts.
- Save while a reply is running. The page asks first; Cancel saves nothing.
- Remove the Telegram token and save. After the restart, the Telegram channel does not start.
- Open the page from your phone, or send the save through the page server with curl. Saving is refused.
- In the Mac app, the menu-bar "Credentials…" opens the page, and a save restarts the app's harness.
- The per-machine settings file stays readable by its owner only after a save.
