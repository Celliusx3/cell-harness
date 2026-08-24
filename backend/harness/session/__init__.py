"""Sessions — the append-only log, and everything around it.

Named by role, the way cell-bot names its features, rather than by architectural
layer:

    models.py            the data: events, and the header beside them
    log.py               `Session` — the append-only log itself
    derive.py            log -> the messages a model is sent
    repair.py            results for calls a dead process never answered

    repository.py        the storage port (Protocol) + its failures
    repositories/        one file per backend — `jsonl.py` today
    service.py           `SessionService` — when to write, repair on resume

`SessionService` depends on the `SessionRepository` Protocol, never on a concrete
backend, so a SQLite store is a new file in `repositories/` plus one line in
`cli.py`. `test_layering.py` enforces the other half: the first four modules know
nothing about storage, so what a conversation *is* cannot come to depend on where
it happens to be kept.

The invariant the whole design upholds: **model history is derived from the log**
(`derive_messages`), never stored beside it. Resume, fork, and compaction are
consequences of that rather than features to build and keep in sync.
"""
