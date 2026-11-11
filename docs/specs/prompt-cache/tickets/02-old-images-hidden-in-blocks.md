# 02 · Old images are hidden in logged blocks that never come back

**Status.** done

**What to build.** A new session event `ImagesHidden`, type `images/hidden`, with `turn` and `through: int`. It means "the first `through` images of the chat's log are hidden". Images count in log order, across person messages and tool results. The largest `through` in the log wins, so a hide never comes back. Its fold lives beside the event in a new `session/images.py`, as compaction's do.

`derive_messages` turns every hidden image into the existing note. It no longer works out the newest 10 images or 12 MB, so `IMAGES_KEPT` and `IMAGE_BYTES_KEPT` go. A model that cannot see images still gets every image as a note.

The OpenAI adapter checks the images it is about to send, oldest first. Over 600 images or 20 MB of base64 data, it sends nothing and ends with a `Failed` of a new code. The `Failed` carries how many of the shown images to hide: the excess, rounded up to 20 images or 10 MB.

`_failure_or_retry` in `runtime/turn.py` takes that code. It appends one `ImagesHidden` whose `through` covers that many more of the shown images, then returns `RetryStep`. When no shown image is left to hide, the failure stands.

Files: `session/images.py` (new), `session/models.py`, `session/derive.py`, `llm/models/stream.py`, `llm/adapters/openai/client.py` (or a new limit module beside it), `runtime/turn.py`, and their tests.

**Checks.**

- A unit test of the adapter's check: 25 small images pass, and 601 images ask for 20 to be hidden.
- Images just over 20 MB ask for at least 10 MB.
- An integration test runs a turn on a fake model that views one large image per step. Between two hides, each request starts with the whole previous request. Each hide covers at least 10 MB.
- A switch to another model that sees images keeps the same images hidden. So does a compaction.
- The replay script on the page 4 log shows no prefix break between hides.
- `make lint` and `make test` stay green.

**Blocked by.** none
