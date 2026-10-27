# 06 Move the settings file's keys into the keyring

**Status:** open

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
