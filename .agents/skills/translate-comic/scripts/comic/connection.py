"""A session with PhotoCraft's headless server, one JSON line each way."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from io import BufferedRWPair
from itertools import count
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, ValidationError

REPLY_TIMEOUT_SECONDS = 60.0


class PhotoCraftError(RuntimeError):
    """PhotoCraft could not be reached, refused a request, or did not answer as asked."""


class Request(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    method: str
    params: dict[str, JsonValue]


class Answer(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    ok: Literal[True]
    result: JsonValue


class Refusal(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    ok: Literal[False]
    error: str


class SignInResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    authenticated: Literal[True]


class SignInReply(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: Literal[True]
    result: SignInResult


REPLY: TypeAdapter[Answer | Refusal] = TypeAdapter(
    Annotated[Answer | Refusal, Field(discriminator="ok")]
)


class Address(NamedTuple):
    host: str
    port: int


def address(addr: str) -> Address:
    """The host and port of a `host:port` address."""
    host, colon, port = addr.rpartition(":")
    if not colon or not host or not port.isdigit():
        raise PhotoCraftError(f"PhotoCraft's address {addr!r} is not host:port")
    return Address(host, int(port))


@dataclass(frozen=True)
class Session:
    """One connection to PhotoCraft: each request is one line out, answered by one line back."""

    stream: BufferedRWPair
    ids: Iterator[int]

    def request(self, method: str, params: dict[str, JsonValue]) -> JsonValue:
        """The result of one request; an `ok: false` reply raises with PhotoCraft's error."""
        sent = Request(id=next(self.ids), method=method, params=params)
        reply = REPLY.validate_json(self._reply_line(sent))
        if reply.id != sent.id:
            raise PhotoCraftError(
                f"PhotoCraft answered request {reply.id} when request {sent.id} ({method}) was sent"
            )
        if isinstance(reply, Refusal):
            raise PhotoCraftError(reply.error)
        return reply.result

    def sign_in(self, token: str) -> None:
        """Send `auth`; any reply but `authenticated: true` means the sign-in was refused."""
        line = self._reply_line(Request(id=next(self.ids), method="auth", params={"token": token}))
        try:
            SignInReply.model_validate_json(line)
        except ValidationError as refusal:
            raise PhotoCraftError(
                f"PhotoCraft refused the sign-in with this token: {line.decode().strip()}"
            ) from refusal

    def _reply_line(self, sent: Request) -> bytes:
        self.stream.write(sent.model_dump_json().encode() + b"\n")
        self.stream.flush()
        try:
            line = self.stream.readline()
        except TimeoutError as silence:
            raise PhotoCraftError(
                f"PhotoCraft did not answer {sent.method} within {REPLY_TIMEOUT_SECONDS:g} seconds"
            ) from silence
        if not line:
            raise PhotoCraftError(
                f"PhotoCraft closed the connection before answering {sent.method}"
            )
        return line


@contextmanager
def connected(addr: str, token: str) -> Iterator[Session]:
    """A session with PhotoCraft's server at `host:port`, signed in with `token` first."""
    host, port = address(addr)
    try:
        connection = socket.create_connection((host, port), timeout=REPLY_TIMEOUT_SECONDS)
    except OSError as unreachable:
        raise PhotoCraftError(
            f"PhotoCraft is not reachable at {addr}: {unreachable}"
        ) from unreachable
    with connection, connection.makefile("rwb") as stream:
        session = Session(stream=stream, ids=count(1))
        session.sign_in(token)
        yield session
