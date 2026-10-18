"""A session with PhotoCraft's headless server: it signs in first, and an error reply raises."""

from __future__ import annotations

import json
import socket
import threading

import pytest

from comic.connection import PhotoCraftError, connected

TOKEN = "a" * 64


class FakeServe:
    """PhotoCraft's `serve` on a loopback port: one JSON line in, one out, `auth` first."""

    def __init__(self) -> None:
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addr = f"127.0.0.1:{self.listener.getsockname()[1]}"
        self.received: list[dict] = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        conn, _ = self.listener.accept()
        with conn, conn.makefile("rwb") as stream:
            for line in stream:
                request = json.loads(line)
                self.received.append(request)
                stream.write((json.dumps(self._answer(request)) + "\n").encode())
                stream.flush()

    def _answer(self, request: dict) -> dict:
        signed_in = any(r["method"] == "auth" for r in self.received[:-1])
        if request["method"] == "auth":
            ok = request["params"]["token"] == TOKEN
            return {"id": request["id"], "ok": ok, "result": {"authenticated": ok}}
        if not signed_in:
            return {"id": request["id"], "ok": False, "error": "authentication required"}
        if request["method"] == "doc.open":
            return {"id": request["id"], "ok": True, "result": {"index": 0, "width": 400}}
        return {"id": request["id"], "ok": False, "error": "no such layer LayerId(1)"}


def test_the_first_request_signs_in_with_the_token() -> None:
    serve = FakeServe()

    with connected(serve.addr, TOKEN) as session:
        opened = session.request("doc.open", {"path": "/files/page.png"})

    assert serve.received[0] == {"id": 1, "method": "auth", "params": {"token": TOKEN}}
    assert serve.received[1]["method"] == "doc.open"
    assert opened == {"index": 0, "width": 400}


def test_an_error_reply_raises_in_photocrafts_words() -> None:
    serve = FakeServe()

    with connected(serve.addr, TOKEN) as session, pytest.raises(PhotoCraftError, match="LayerId"):
        session.request("batch", {"steps": []})


def test_a_wrong_token_is_refused_before_any_request() -> None:
    serve = FakeServe()

    with pytest.raises(PhotoCraftError, match="sign"), connected(serve.addr, "b" * 64):
        pass
