# Files

You attach files to a message with the paperclip or by dropping them on the composer; each shows as a chip while it uploads, and above your message once sent: an image as a thumbnail, anything else as a download. The bot is told where each one is saved. A model that can see (`llm.vision: true`) is also shown the attached images.

## Sub-features

- `extract_archive` unpacks a `.zip` or `.cbz` of this chat into numbered files beside it; `make_archive` packs files of this chat, in order, into a new one.
- `view_image` shows the model a PNG or JPEG of this chat, at most 5 MB; it is offered only when the model can see.
- `send_file` hands files of this chat to you: they appear under its tool card, which stays out of the folded turn.
- A file tool given another chat's file refuses it: "… is not a file in this chat".

## How to get to it (user POV)

Attach a picture and ask about it, for example a PNG of a number and "What number is written in the attached image?". Attach a `.cbz` and ask the bot to unpack it, show you page 2, and send it back.

## Driving it with Playwright MCP

`browser_click` "Attach files", then `browser_file_upload` with a path inside the checkout (the tool refuses paths outside it; copy the file into `.playwright-mcp/` first and delete it after). Type the prompt and send. The stored conversation (`curl -s localhost:4996/api/conversations/<id>`) lists the files on the `user/message` event and the images by hash; `GET /api/conversations/<id>/images/<sha256>` serves an image the log names.

## Gotchas

A model that cannot see but runs with `vision: true` fails the whole turn with the provider's "does not support image inputs"; check `config.local.json` before blaming the code. Uploads land under `HARNESS_FILES__ROOT`, which the launch points into `$RUN`.
