#!/usr/bin/env python3
"""The PC's page commands: JSON in on stdin, JSON out, through agent-browser."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

AGENT_BROWSER = "agent-browser"
CDP_PORT = "9222"
STEP_TIMEOUT_SECONDS = 20
SETTLE_MILLISECONDS = "500"
LOAD_TIMEOUT_MILLISECONDS = "10000"
CHROME_DOWN = "CDP not ready"
CDP_FAILED = "CDP discovery methods failed"
UNKNOWN_REF = "Unknown ref"
STALE_REF = "That ref is not on the page any more: the page changed since it was read."
ACTION_KINDS = frozenset({"click", "fill", "type"})

JsonObject = dict[str, object]


class PageError(Exception):
    """A step failed; the message is for the bot."""


@dataclass(frozen=True)
class Action:
    kind: str
    ref: str
    text: str | None


@dataclass(frozen=True)
class Page:
    url: str
    title: str
    tree: str


def text_field(data: JsonObject, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise PageError(f"agent-browser answered without a text {key!r}.")
    return value


def answer_data(stdout: str) -> JsonObject:
    """agent-browser's `data`, or a PageError in words the bot can act on."""
    try:
        answer = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise PageError(
            f"agent-browser answered with something that is not JSON: {stdout!r}"
        ) from err
    if not isinstance(answer, dict):
        raise PageError("agent-browser answered with something that is not an object.")
    if answer.get("success") is True and isinstance(answer.get("data"), dict):
        return answer["data"]
    raise PageError(failure_message(str(answer.get("error") or "agent-browser failed.")))


def failure_message(error: str) -> str:
    if CDP_FAILED in error:
        return f"{CHROME_DOWN}: {error}"
    if error.startswith(UNKNOWN_REF):
        return STALE_REF
    return error


def agent_browser(*arguments: str) -> JsonObject:
    """One agent-browser step on the Chromium on this PC's screen."""
    try:
        completed = subprocess.run(
            [AGENT_BROWSER, "--json", *arguments],
            capture_output=True,
            text=True,
            timeout=STEP_TIMEOUT_SECONDS,
            env={**os.environ, "AGENT_BROWSER_CDP": CDP_PORT},
            check=False,
        )
    except subprocess.TimeoutExpired as err:
        raise PageError(f"The page did not answer within {STEP_TIMEOUT_SECONDS} seconds.") from err
    return answer_data(completed.stdout)


def as_ref(ref: str) -> str:
    return ref if ref.startswith("@") else f"@{ref}"


def settle() -> None:
    """Give a page the last action opened time to load; a slow page is read as far as it got."""
    agent_browser("wait", SETTLE_MILLISECONDS)
    try:
        agent_browser("wait", "--load", "load", "--timeout", LOAD_TIMEOUT_MILLISECONDS)
    except PageError:
        return


def read_page() -> Page:
    tree = text_field(agent_browser("snapshot"), "snapshot")
    url = text_field(agent_browser("get", "url"), "url")
    title = text_field(agent_browser("get", "title"), "title")
    return Page(url=url, title=title, tree=tree)


def parse_action(raw: object) -> Action:
    if not isinstance(raw, dict):
        raise PageError("Each action is an object.")
    kind, ref, text = raw.get("kind"), raw.get("ref"), raw.get("text")
    if kind not in ACTION_KINDS or not isinstance(ref, str) or not ref:
        raise PageError(f"An action needs a kind of click, fill or type, and a ref: {raw!r}")
    if (kind == "click") != (text is None) or (text is not None and not isinstance(text, str)):
        raise PageError(f"click takes no text; fill and type need text: {raw!r}")
    return Action(kind=str(kind), ref=ref, text=text)


def run_action(action: Action) -> None:
    extra = () if action.text is None else (action.text,)
    agent_browser(action.kind, as_ref(action.ref), *extra)


def navigate(arguments: JsonObject) -> JsonObject:
    data = agent_browser("open", text_field(arguments, "url"))
    return {"ok": True, "url": text_field(data, "url"), "title": text_field(data, "title")}


def snapshot(_: JsonObject) -> JsonObject:
    page = read_page()
    return {"ok": True, "url": page.url, "title": page.title, "tree": page.tree}


def act(arguments: JsonObject) -> JsonObject:
    raw = arguments.get("actions")
    if not isinstance(raw, list) or not raw:
        raise PageError("act needs a non-empty list of actions.")
    actions = [parse_action(item) for item in raw]
    for done, action in enumerate(actions):
        try:
            run_action(action)
        except PageError as err:
            return {"ok": False, "error": str(err), "completed": done}
    settle()
    page = read_page()
    return {
        "ok": True,
        "url": page.url,
        "title": page.title,
        "tree": page.tree,
        "completed": len(actions),
    }


COMMANDS: dict[str, Callable[[JsonObject], JsonObject]] = {
    "navigate": navigate,
    "snapshot": snapshot,
    "act": act,
}


def parse_arguments(stdin: str) -> JsonObject:
    try:
        arguments = json.loads(stdin or "{}")
    except json.JSONDecodeError as err:
        raise PageError("The arguments on stdin are not JSON.") from err
    if not isinstance(arguments, dict):
        raise PageError("The arguments on stdin are not an object.")
    return arguments


def answer(argv: Sequence[str], stdin: str) -> JsonObject:
    """The reply for one command; a failure is an `ok: false` reply, never a raise."""
    if len(argv) != 1 or argv[0] not in COMMANDS:
        return {"ok": False, "error": f"Usage: pc-page {'|'.join(COMMANDS)}"}
    try:
        return COMMANDS[argv[0]](parse_arguments(stdin))
    except PageError as err:
        return {"ok": False, "error": str(err)}


def main() -> None:
    print(json.dumps(answer(sys.argv[1:], sys.stdin.read())))


if __name__ == "__main__":
    main()
