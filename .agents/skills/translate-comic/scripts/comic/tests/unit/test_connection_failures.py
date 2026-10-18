"""PhotoCraft out of reach, silent, hanging up or answering out of turn raises in plain words."""

from __future__ import annotations

import socket
import threading

import pytest

from comic import connection
from comic.connection import PhotoCraftError, connected

TOKEN = "a" * 64
SIGNED_IN = '{"id": 1, "ok": true, "result": {"authenticated": true}}'


class Scripted:
    """A loopback server that answers each line with the next scripted reply, then hangs up."""

    def __init__(self, replies: list[str]) -> None:
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addr = f"127.0.0.1:{self.listener.getsockname()[1]}"
        threading.Thread(target=self._serve, args=(replies,), daemon=True).start()

    def _serve(self, replies: list[str]) -> None:
        conn, _ = self.listener.accept()
        with conn, conn.makefile("rwb") as stream:
            for reply in replies:
                stream.readline()
                stream.write(reply.encode() + b"\n")
                stream.flush()
            stream.readline()


def test_an_address_without_a_port_is_refused() -> None:
    with pytest.raises(PhotoCraftError, match="host:port"), connected("photocraft", TOKEN):
        pass


def test_nothing_listening_says_where_it_looked() -> None:
    closed = socket.create_server(("127.0.0.1", 0))
    addr = f"127.0.0.1:{closed.getsockname()[1]}"
    closed.close()

    with pytest.raises(PhotoCraftError, match=f"not reachable at {addr}"), connected(addr, TOKEN):
        pass


def test_a_refused_sign_in_carries_photocrafts_reply() -> None:
    serve = Scripted(['{"id": 1, "ok": false, "error": "invalid token"}'])

    refused = pytest.raises(PhotoCraftError, match="refused the sign-in.*invalid token")
    with refused, connected(serve.addr, TOKEN):
        pass


def test_a_server_that_hangs_up_names_the_request_it_left() -> None:
    serve = Scripted([SIGNED_IN])

    with connected(serve.addr, TOKEN) as session, pytest.raises(PhotoCraftError, match="doc.open"):
        session.request("doc.open", {"path": "/files/page.png"})


def test_a_silent_server_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(connection, "REPLY_TIMEOUT_SECONDS", 0.2)
    silent = socket.create_server(("127.0.0.1", 0))

    timed_out = pytest.raises(PhotoCraftError, match="did not answer auth within 0.2 seconds")
    with timed_out, connected(f"127.0.0.1:{silent.getsockname()[1]}", TOKEN):
        pass
    silent.close()


def test_a_reply_to_another_request_is_not_taken_as_this_ones() -> None:
    serve = Scripted([SIGNED_IN, '{"id": 99, "ok": true, "result": null}'])

    with connected(serve.addr, TOKEN) as session, pytest.raises(PhotoCraftError, match="99"):
        session.request("session.list", {})
