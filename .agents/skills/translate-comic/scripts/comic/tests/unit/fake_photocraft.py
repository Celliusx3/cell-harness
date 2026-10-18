"""A stand-in for PhotoCraft's `serve` on a loopback port: enough of it to erase and letter."""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageDraw

TOKEN = "c" * 64
GLYPH_WIDTH = 0.6
LINE_HEIGHT = 1.2
CONTENT_AWARE = "#ffffff"


class Refusal(Exception):
    """What PhotoCraft answers as `ok: false`."""


@dataclass(frozen=True)
class TextLayer:
    """A text layer: one line, as wide as its letters, centred across its box and at its top."""

    text: str
    box: tuple[int, int, int, int]
    size: float
    move: tuple[int, int] = (0, 0)

    def bounds(self) -> list[float]:
        x, y, w, _ = self.box
        width, height = GLYPH_WIDTH * self.size * len(self.text), LINE_HEIGHT * self.size
        left, top = x + (w - width) / 2 + self.move[0], y + self.move[1]
        return [left, top, left + width, top + height]


class FakePhotoCraft:
    """One shared session for every connection; a batch stops at a failure when told to."""

    def __init__(self, refusing: frozenset[str] = frozenset(), *, stops: bool = False) -> None:
        self.refusing = refusing
        self.always_stops = stops
        self.documents: list[Image.Image] = []
        self.layers: dict[int, TextLayer] = {}
        self.selection: list[tuple[int, int, int, int]] = []
        self.active = -1
        self.batches: list[dict] = []
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.addr = f"127.0.0.1:{self.listener.getsockname()[1]}"
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        while True:
            conn, _ = self.listener.accept()
            with conn, conn.makefile("rwb") as stream:
                for line in stream:
                    request = json.loads(line)
                    stream.write((json.dumps(self._answer(request)) + "\n").encode())
                    stream.flush()

    def _answer(self, request: dict) -> dict:
        try:
            result = self._method(request["method"], request["params"])
        except Refusal as refusal:
            return {"id": request["id"], "ok": False, "error": str(refusal)}
        return {"id": request["id"], "ok": True, "result": result}

    def _method(self, method: str, params: dict) -> object:
        match method:
            case "auth":
                if params["token"] != TOKEN:
                    raise Refusal("invalid token")
                return {"authenticated": True}
            case "doc.open":
                with Image.open(params["path"]) as image:
                    self.documents.append(image.convert("RGB"))
                self.active = len(self.documents) - 1
                width, height = self.documents[-1].size
                name = Path(params["path"]).name
                return {"index": self.active, "width": width, "height": height, "name": name}
            case "batch":
                self.batches.append(params)
                stops = self.always_stops or params.get("stopOnError", True)
                return self._batch(params["steps"], stops)
            case "doc.save":
                self.documents[params["index"]].save(params["path"])
                return {"path": params["path"], "warnings": []}
            case "doc.close":
                self.documents.pop(params["index"])
                return {"documents": len(self.documents)}
        raise Refusal(f"unknown method {method}")

    def _batch(self, steps: list[dict], stops: bool) -> dict:
        results: list[dict] = []
        for step in steps:
            try:
                results.append({"ok": True, "result": self._command(step)})
            except Refusal as refusal:
                results.append({"ok": False, "error": str(refusal)})
                if stops:
                    break
        failed = sum(not result["ok"] for result in results)
        return {"completed": len(results) - failed, "failed": failed, "results": results}

    def _command(self, step: dict) -> object:
        command, params = step["command"], step["params"]
        if command in self.refusing:
            raise Refusal(f"command `{command}` is not available right now")
        match command:
            case "document.activate":
                if not 0 <= params["document"] < len(self.documents):
                    raise Refusal(f"no document {params['document']}")
                self.active = params["document"]
            case "select.rect":
                rect = (params["x"], params["y"], params["width"], params["height"])
                self.selection = [*self.selection, rect] if params["mode"] == "add" else [rect]
            case "edit.fill":
                self._fill(params.get("color", CONTENT_AWARE))
            case "select.deselect":
                self.selection = []
            case "type.create":
                layer = len(self.layers) + 1
                self.layers[layer] = TextLayer(params["text"], tuple(params["box"]), params["size"])
                return {"bounds": self.layers[layer].bounds(), "layer": layer}
            case "type.info":
                text = self._layer(params["layer"])
                lines = [{"start": 0, "end": len(text.text)}]
                return {"lines": lines, "bounds": text.bounds(), "pxPerPt": 1.0}
            case "type.setStyle":
                self.layers[params["layer"]] = replace(
                    self._layer(params["layer"]), size=params["size"]
                )
            case "type.edit":
                text = self._layer(params["layer"])
                dx, dy = params["move"]
                self.layers[params["layer"]] = replace(
                    text, move=(text.move[0] + dx, text.move[1] + dy)
                )
            case _:
                raise Refusal(f"unknown command `{command}`")
        return None

    def _fill(self, colour: str) -> None:
        if not self.selection:
            raise Refusal("no selection")
        pen = ImageDraw.Draw(self.documents[self.active])
        for x, y, w, h in self.selection:
            pen.rectangle((x, y, x + w - 1, y + h - 1), fill=colour)

    def _layer(self, layer: int) -> TextLayer:
        if layer not in self.layers:
            raise Refusal(f"no such layer LayerId({layer})")
        return self.layers[layer]
