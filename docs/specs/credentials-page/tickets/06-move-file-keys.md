# 06 Move the settings file's keys into the keyring

**Status:** done, except the by-hand Mac app check

**What to build.**

- On start, the settings file's model key becomes the Default model LLM credential, with the file's endpoint and model.
- Its Telegram and Discord tokens become the Telegram and Discord credentials.
- The keys are then removed from the per-machine settings file, which keeps every other value.
- Starting no longer needs the model key in the file. With no Default model after the move, the harness refuses to start and says how to add one.
- The Mac app's first-start window saves the key through the harness instead of writing the file.

**Checks.**

- A test: a file holding all three keys starts the harness with three credentials, and the file holds none of them afterwards.
- A second start does not move anything twice.
- By hand: the Mac app's first start asks for a key and chats, and a second start does not ask again.

**Blocked by.** 05

**Notes.**

- The Mac app's first-start window still writes the key into the per-machine settings file, and the harness moves it into the keyring when it starts. This replaces "saves through the harness" above: the window asks before the harness runs, so there is no harness to save through yet.
- The window shows only when that file holds no `llm.api_key` and the keyring at the committed `secrets.path` holds no LLM credential named `default_model`.
- The by-hand Mac app check has not run: a run on this Mac would share its data folder and ports with the installed app. The harness alone was checked by hand on port 4986 with a scratch settings file.
