# The OpenAI adapter in its own folder, Python style, with its models apart

## Problem

The adapter's seven files sit flat in one folder. One provider's files are told apart by a prefix, two of its files carry no prefix at all, and the names are jargon a reader must open to decode: wire for the request, frames for the streamed lines, calls for joining tool-call pieces. The outgoing request is built in two files, the call joiner takes its data shape from the line reader, and the client's one function still sends the request, reads the streamed lines byte by byte and turns them into events, at a complexity of 11.

## What changes for you

Nothing a person sees changes. The model is sent the same requests and its replies are read the same way.

How the code reads after it, with one example: OpenAI streams back a tool call in three pieces.

1. The OpenAI adapter sits in its own folder. The shapes it reads from OpenAI sit in a models folder, one file per shape, the way the model package keeps its own vocabulary; the logic sits beside the client, one file per subject, with a leading underscore on each file only the adapter uses.
2. The client builds the request from the request file and hands the reply's lines to the streaming file.
3. The streaming file turns each line into a chunk, OpenAI's own name for it, and skips the lines it skips today.
4. The tool-calls file joins the three tool deltas into one call; the client hands back the text, the call, and the end of the reply.
5. The rest of the app still reaches the adapter only through the adapters door, under the same three names.

## Decisions

- Python style, as the person chose: short lowercase module names named for their subject, a leading underscore on internal modules, and no folder holding a single file, as the OpenAI Python SDK lays itself out (its `_client.py`, `_streaming.py`, `_exceptions.py`).
- The models apart from the logic, as the person chose: one file per shape in a models folder, as the model package's own models folder and the OpenAI SDK's types folder (`types/chat/chat_completion_chunk.py`) do.
- The streamed shapes take OpenAI's names: a chunk carrying tool deltas, after OpenAI's own words, short because the models folder already says whose they are.
- The adapters door stays the only door; the provider folder's first file holds only its description.
- The client holds every call the adapter makes to OpenAI, the chat stream and the model listing, as the OpenAI SDK's one client does, so the endpoint address and its key are built in one place.
- A chunk the provider sent as an error carries that line as its error text, in place of a failed flag, so the client reports the same reason and code as today.

## Out of scope

- The complexity limit for the whole backend; it follows as its own change.
- Any change to what is sent or how a reply is read.

## How we will know it works

- The 1455 backend tests pass, and lint passes, after every ticket.
- After the first ticket, a search for the old adapter paths and names finds nothing outside the specs.
- After the second, the client's streaming function is under a complexity of 10, and the streaming file is tested by handing it lines, with no server.
- Importing one of the adapter's underscored files from the web code, on purpose, fails the layering test.
