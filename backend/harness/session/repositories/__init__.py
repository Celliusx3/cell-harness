"""Concrete storage backends, each implementing `session.repository.SessionRepository`.

One file per backend, the way `llm/adapters/` holds model providers and
`tools/native/` holds tools. A folder rather than a single module because a
second backend is a new file here and nothing else: `SessionService` is handed a
repository and never names one, so choosing a different store is a line in
`cli.py`.

    jsonl.py   an append-only JSONL file per session

The likely next one is SQLite, when searching message *content* starts to matter.
Listing conversations does not need it — the header is line 1 of each file.
"""
