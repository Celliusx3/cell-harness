# Saved keys

A bot that needs a key calls `ask_for_secret` with a kind: `custom` (a website's API key), `llm` (a model provider's key), `telegram` or `discord` (the app's bot token). A card under the call names what it is for and takes the key in a hidden box. Save seals it in the one keyring as that kind of credential; the model reads back only the name. A custom key is one that bot may use: it then calls `fetch_with_secret`, which asks first like any write, and the server adds the key to the request.

## Sub-features

- The card: label, "Sent only to <host>. The assistant never sees it." (an `llm` card says to pick it for a bot in Edit bot, and shows Endpoint, Model and "Can see images" filled in and editable), a password box and Save; no decline button. Answered, it reads "Saved as <name>."; typing a message instead reads "Skipped. You continued without saving."
- A key that breaks the rule (8 to 16,384 printable characters) is refused on the card with the rule.
- A saved key is a row of its kind on the Credentials page ("Settings", then "Credentials"), with its site and its bots. See [credentials.md](credentials.md).
- A bot not allowed a key gets `NOT_ALLOWED`; ticking the key under "Keys this bot can use" on its Edit bot page allows it, saved at once.
- Telegram and Discord get a link to the card's page, saying not to paste the key into the chat.

## How to get to it (user POV)

Ask for something behind a key, for example "I have an httpbin token. Check it against https://httpbin.org/bearer for me." Paste any made-up token of 8 or more characters.

## Driving it with Playwright MCP

Send the prompt, `browser_snapshot` to find the textbox labelled with the card's label (placeholder "Paste the key here"), `browser_type` the token, `browser_click` "Save", then `browser_wait_for` "Allow once" and click it. httpbin echoes the token, so the reply shows `"token": "[secret]"`.

## Gotchas

Search for the token afterwards: `grep -r <token> "$RUN/harness" "$RUN/backend.log"` must find nothing. The secrets file is `$RUN/harness/secrets.json`, sealed under `$RUN/encryption_key`; a copy started with another key cannot open what an earlier one saved.
