# Setup

The first screen when the keyring holds no Default model. It fills the window with no sidebar, asks for one API key, and saves it as the Default model through the Credentials save. The chat then opens in the same window, with no restart.

## Sub-features

- Every chat page goes to `/setup` while no Default model is saved. `/setup` goes to the Assistant's chat once one is.
- The screen says "Welcome to Cell Harness" and "Paste your API key to start.", with an "API key" box, "Use another provider" and "Start".
- "Use another provider" shows "Endpoint" and "Model", filled with the harness's configured `llm.base_url` and `llm.model`. Until it is clicked, Start sends those values.
- While it saves, the button says "Starting…". A refusal shows the harness's message under the fields.
- A page that cannot reach the harness directly shows "Finish setup on the Mac that runs Cell Harness" and no form. The Mac's network address is one such page.
- No key is checked with the provider. A wrong key shows at the first reply as "provider returned 401: …", and is fixed with Edit on the Credentials page.

## How to get to it (user POV)

Open the chat before any model key is saved. In the Mac app, the first start opens on it.

## Driving it with Playwright MCP

The launch above copies a model key into `$RUN/config.local.json`, so the copy never shows setup. To show it, give the copy no model key: write `{}` to `$RUN/config.local.json` and delete `$RUN/harness/secrets.json` before the launch. Never use the person's own key on this screen: the typed key lands in the tool call.

Point the copy at a fake OpenAI-compatible endpoint on this Mac instead. Set `HARNESS_LLM__BASE_URL` and `HARNESS_LLM__MODEL` for the backend, or type them after "Use another provider". The endpoint answers `POST <base>/chat/completions` with a streamed reply for one fake key and 401 for any other.

`browser_navigate` to `/`. The URL becomes `/setup`. Type the fake key into "API key" and click "Start". The URL becomes `/c/assistant`. To see the note, open the copy at the Mac's network address, from `ipconfig getifaddr en0`, port 4997.

## Gotchas

`/setup` reads `GET /api/credentials` through the page server, then checks the harness directly on port 4996. From a page that is not on `localhost` or `127.0.0.1`, the browser blocks that check, and its console shows a CORS error. That error is how the page learns it cannot save.
