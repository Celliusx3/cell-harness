"""`/api/relay/{id}/…`: a loopback page and its websocket, through a relay."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from websockets.sync.server import Server, ServerConnection, serve

from harness.mcp.relay import RELAY_TTL_SECONDS, Relays, Upstream
from harness.web.routes.relay import build_router

GREETING = b"RFB 003.008\n"


class Now:
    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds


class Page(BaseHTTPRequestHandler):
    """A noVNC stand-in: one module script, and a 404 for anything else."""

    asked: list[str] = []

    def do_GET(self) -> None:
        Page.asked.append(self.path)
        found = self.path.startswith("/core/rfb.js")
        body = b"export default class RFB {}" if found else b"no such file"
        self.send_response(200 if found else 404)
        self.send_header("Content-Type", "text/javascript" if found else "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


ENDED = threading.Event()


def echo(connection: ServerConnection) -> None:
    """A websockify stand-in: greets, answers every frame in kind, and hangs up on "bye"."""
    assert connection.request is not None
    connection.send(GREETING)
    connection.send(f"path {connection.request.path}")
    for message in connection:
        if message == "bye":
            break
        connection.send(b"echo " + message if isinstance(message, bytes) else f"echo {message}")
    ENDED.set()


@pytest.fixture
def page() -> Iterator[Upstream]:
    Page.asked = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield Upstream(host="127.0.0.1", port=server.server_address[1])
    server.shutdown()
    server.server_close()


@pytest.fixture
def socket() -> Iterator[Upstream]:
    ENDED.clear()
    server: Server = serve(echo, "127.0.0.1", 0, subprotocols=["binary"])
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield Upstream(host="127.0.0.1", port=server.socket.getsockname()[1])
    server.shutdown()


@pytest.fixture
def now() -> Now:
    return Now()


@pytest.fixture
def relays(now: Now) -> Relays:
    return Relays(now=now)


@pytest.fixture
def client(relays: Relays) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(build_router(relays))
    with TestClient(app) as client:
        yield client


def test_a_page_is_fetched_from_its_origin_with_status_type_and_body(
    client: TestClient, relays: Relays, page: Upstream
) -> None:
    relay_id = relays.open(page)

    response = client.get(f"/api/relay/{relay_id}/core/rfb.js?v=1&x=a%20b")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/javascript"
    assert response.content == b"export default class RFB {}"
    assert response.headers["access-control-allow-origin"] == "*"
    assert Page.asked == ["/core/rfb.js?v=1&x=a%20b"]


def test_an_upstream_404_is_passed_on(client: TestClient, relays: Relays, page: Upstream) -> None:
    response = client.get(f"/api/relay/{relays.open(page)}/nothing.html")

    assert response.status_code == 404
    assert response.headers["content-type"] == "text/plain"
    assert response.headers["access-control-allow-origin"] == "*"


def test_an_unknown_relay_is_not_found(client: TestClient, page: Upstream) -> None:
    assert client.get("/api/relay/nope/core/rfb.js").status_code == 404
    assert Page.asked == []


def test_an_expired_relay_is_not_found(
    client: TestClient, relays: Relays, now: Now, page: Upstream
) -> None:
    relay_id = relays.open(page)
    now.seconds += RELAY_TTL_SECONDS

    assert client.get(f"/api/relay/{relay_id}/core/rfb.js").status_code == 404
    assert Page.asked == []


def test_an_origin_that_does_not_answer_is_a_bad_gateway(
    client: TestClient, relays: Relays
) -> None:
    relay_id = relays.open(Upstream(host="127.0.0.1", port=1))

    assert client.get(f"/api/relay/{relay_id}/embed.html").status_code == 502


def test_frames_pass_both_ways_and_the_chosen_subprotocol_comes_back(
    client: TestClient, relays: Relays, socket: Upstream
) -> None:
    relay_id = relays.open(socket)
    url = f"/api/relay/{relay_id}/websockify?token=Zk3_q-9x"

    with client.websocket_connect(url, subprotocols=["binary"]) as screen:
        greeting = screen.receive_bytes()
        path = screen.receive_text()
        screen.send_bytes(b"\x03\x00")
        echoed_bytes = screen.receive_bytes()
        screen.send_text("hello")
        echoed_text = screen.receive_text()

    assert screen.accepted_subprotocol == "binary"
    assert greeting == GREETING
    assert path == "path /websockify?token=Zk3_q-9x"
    assert echoed_bytes == b"echo \x03\x00"
    assert echoed_text == "echo hello"


def test_the_browser_hanging_up_closes_the_upstream(
    client: TestClient, relays: Relays, socket: Upstream
) -> None:
    url = f"/api/relay/{relays.open(socket)}/websockify"
    with client.websocket_connect(url, subprotocols=["binary"]) as screen:
        screen.receive_bytes()

    assert ENDED.wait(5)


def test_the_upstream_hanging_up_closes_the_browser(
    client: TestClient, relays: Relays, socket: Upstream
) -> None:
    url = f"/api/relay/{relays.open(socket)}/websockify"
    with client.websocket_connect(url, subprotocols=["binary"]) as screen:
        screen.receive_bytes()
        screen.receive_text()
        screen.send_text("bye")
        with pytest.raises(WebSocketDisconnect):
            screen.receive_text()


def test_an_unknown_relay_closes_the_socket_with_1008(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect("/api/relay/nope/websockify", subprotocols=["binary"]),
    ):
        pass

    assert closed.value.code == 1008


def test_an_expired_relay_closes_the_socket_with_1008(
    client: TestClient, relays: Relays, now: Now, socket: Upstream
) -> None:
    relay_id = relays.open(socket)
    now.seconds += RELAY_TTL_SECONDS

    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(f"/api/relay/{relay_id}/websockify"),
    ):
        pass

    assert closed.value.code == 1008


def test_an_upstream_that_refuses_the_socket_closes_the_browser_with_1011(
    client: TestClient, relays: Relays, page: Upstream
) -> None:
    relay_id = relays.open(page)

    with (
        pytest.raises(WebSocketDisconnect) as closed,
        client.websocket_connect(f"/api/relay/{relay_id}/websockify"),
    ):
        pass

    assert closed.value.code == 1011
