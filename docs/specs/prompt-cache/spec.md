# Old images are hidden in blocks, so the prompt cache keeps working

Issue #56.

## Problem

On a long turn where a bot views an image on almost every step, most of each request is billed at the full input price. The bot shows the model only its 10 newest images. So each new image turns the oldest one into a note, and that changes an earlier message on almost every step. The provider reuses a cached request only up to the first changed token. So the 10 kept images and everything after them are paid in full on each step. We also drop the provider's count of cached tokens, so no log shows the real hit rate.

We replayed the logs of the two runs in the issue. Today the cached part can reach at most 66% of input on page 4, and 54% on page 5. With the oldest images hidden in blocks, the same runs reach about 91% and 88%. The input bill then falls to about 40% of today's. These numbers are inferred from the replay, and assume the provider caches every repeated start.

## What changes for you

1. You ask the Manga Translator to translate a long comic. It views one page per step, as today.
2. The bot keeps every page in view until the request reaches 600 images or 20 MB of images.
3. Past that limit, the oldest pages are hidden in one block of at least 20 images or 10 MB. Until the next block, each step only adds to the end of the request.
4. In place of each hidden page the bot reads one note. The note tells it not to describe the page from memory. It also tells it to get the page again with a tool, or to ask you for it.
5. You switch the bot to a model with a larger window, or the chat is compacted. The hidden pages stay hidden.
6. After the turn, each reply's usage in the log shows how many input tokens came from the cache.

Nothing on the screen changes.

## Decisions

- Which images are hidden is a logged event, and it only grows. DeepSeek Harness records an image offload event and never restores an image. browser-use also keeps its pruning. opencode and the Anthropic computer-use demo work it out again on every request.
- The event says "the first N images of the chat are hidden", one number. DeepSeek Harness names each image by message and position, because its log can replace a message. Ours never replaces a message, so one number is enough (one source).
- The model adapter checks the limit before it sends. Over the limit, it refuses the request with the number of images to hide. The turn then records the hide and sends the request again, without counting a failure. DeepSeek Harness does this, and our "too big, compact, then retry" path already has this shape. opencode and the Anthropic demo check before they send instead.
- The limits are DeepSeek Harness's for images sent inside the request: 600 images, or 20 MB of image data as sent. A hide removes at least 20 images or 10 MB. The same limits apply to every model, with no setting. opencode drops in blocks too, at 25 MB down to 15 MB.
- A provider that itself refuses a request for too many images also gets one block hidden and one retry, when its error says so. To decide at approval: this needs the provider's error wording, and we have not seen one yet.
- The note is one fixed sentence, close to opencode's: "This image was removed to reduce the request size and is no longer visible. Do not make claims about its contents from memory. If needed, retrieve it again with an available tool or ask the user to attach it again." A file you attached already has its path in the same message, so the note does not repeat it.
- Cached tokens are recorded beside the input tokens, which keep their meaning (all input, cached or not). OpenRouter's usage reports `cached_tokens` as part of `prompt_tokens`. DeepSeek Harness, opencode, browser-use and Codex all record cached input tokens.
- To decide at approval: each request also sends the chat's id as OpenRouter's `session_id`. OpenRouter's docs say this keeps a chat's requests on one provider from the first request, so its cache can be reused. Other providers may refuse an unknown field.
- A model that cannot see images still gets every image as a note, as today.

## Out of scope

- Showing the cache hit rate on the screen.
- A per-model image limit or setting.
- Shrinking each image before it is sent, as DeepSeek Harness does.
- Sending images as uploaded files instead of inside the request.
- The tool list changing when the bot selects a new tool. It changed on 4 of 188 steps in the largest run.
- Making the compaction summary request reuse the conversation's cache.
- Your OpenRouter preset. If it sets a provider order, OpenRouter does not keep the chat on one provider, and the cache can miss whatever we send.

## How we will know it works

- Replay the page 4 and page 5 logs with the replay script. Between two hides, every step's request starts with the whole previous request.
- Run a long comic turn. Read the log. Each reply's usage has cached tokens, and on most steps they are well above half of the input.
- In a test chat with 25 images under the limit, no image is hidden. Push it over the limit, and the oldest block is hidden once. The next steps hide nothing.
- Switch that chat to another model that sees images. The hidden images stay hidden.
- Compact that chat. The hidden images stay hidden.
- `make lint` and `make test` stay green, with coverage at 80% or more.
