# Setup inside the app

## Problem

The Mac app asks for the model key in its own small window. That window uses the Mac's plain font and fields, not the app's look, and the chat then opens in a second window. `make dev` has no setup at all, because the harness stops at start until a model key is in the settings file.

## What changes for you

1. A friend opens Cell Harness for the first time.
2. The app makes its encryption key and starts the harness. The friend sees none of this.
3. The chat window opens on a setup screen. It fills the window, with no sidebar.
4. The screen uses the app's colours and font, light or dark as the Mac is.
5. The screen shows API key, Endpoint and Model boxes and a Start button. Endpoint and Model hold the app's own values.
6. The friend pastes the key and clicks Start.
7. The chat opens in the same window. "hi" gets an answer, with no restart.
8. The key now shows on the Credentials page as the Default model.
9. Someone with another provider sees which endpoint and model the key goes to.
10. They change both values, paste their key and click Start.
11. The next time the app opens, the chat opens straight away.
12. You run `make dev` with an encryption key but no model key. The harness starts.
13. The browser shows the same setup screen.
14. A phone opens the chat before setup. It sees "Finish setup on the Mac that runs Cell Harness", with no form.
15. A friend pastes a wrong key. The first reply shows the provider's error, and they fix the key on the Credentials page.

## Decisions

- A full-page setup screen stands in for the chat until a model key is saved. AnythingLLM and Jan gate their app the same way.
- Setup is needed while the keyring holds no Default model. Jan decides from whether a provider has a key, the same way. AnythingLLM stores a flag instead.
- Start saves the key as the Default model, through the same save the Credentials page uses. AnythingLLM's setup and settings pages share one save the same way.
- The harness starts with no Default model. AnythingLLM's server also starts with no key.
- With no Default model at start, the harness cannot ask the endpoint for its context window. Automatic compaction stays off until the next start, and only a provider overflow compacts in that run. Asking the endpoint at the first turn after setup was declined, because it changes the turn loop.
- A page that cannot save shows a note instead of the form, as the Credentials page turns read-only.
- Setup does not check the key with the provider. The Credentials spec left this out too. LibreChat and LobeHub also show a wrong key as an error in the chat.
- The Mac app writes its encryption key on first start without asking, and it has no setup window of its own.
- `make dev` still needs a hand-written encryption key in its settings file.
- A Telegram or Discord message before setup fails as a model error does today.

## Out of scope

- Checking a key with its provider before it is saved.
- Making the encryption key for `make dev`.
- A "Starting" screen while the harness starts.
- A special reply on Telegram or Discord before setup.
- A way to skip setup.
- Any change to the Credentials page.

## How we will know it works

- Open the Mac app with no data folder. The chat window shows the setup screen, and no other window appears.
- Switch the Mac between light and dark. The setup screen follows, in the same colours as the chat.
- Paste a key and click Start. The chat opens in the same window and answers "hi".
- Open Credentials. The key shows as the Default model, with the app's endpoint and model.
- Quit the app and open it again. The chat opens with no setup screen.
- Change the endpoint and model, and click Start. The Default model shows those values.
- Before setup, open a bot's page or the Skills page. It goes to the setup screen.
- After setup, open the setup screen's address. It goes to the chat.
- Run `make dev` with an encryption key and no model key. The harness starts, and the browser shows the setup screen.
- Open the chat from another device before setup. It shows the note and no form.
- Paste a wrong key. The chat opens, and the first reply shows the provider's error.
- Start with an old settings file that holds an API key. The key moves into the keyring, and no setup screen appears.
