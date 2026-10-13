"""The bash scripts behind the gateway: what each one starts, revokes and refuses."""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import pytest

from computer.gateway import (
    TokenError,
    open_terminal_script,
    release_script,
    screen_url,
    take_control_script,
    terminal_url,
    view_script,
)

HOLD_TOKEN = "Zk3_q-9xYw2PqLm0aBcDeFgHiJkLmNoP"
SOCKETS = "/tmp/rakazo/sockets"
TARGETS = "/tmp/rakazo/desktop-targets"
CONTROL_SOCKET = f"{SOCKETS}/control-1-{hashlib.sha256(HOLD_TOKEN.encode()).hexdigest()[:32]}"
TOKEN_FILE = "/tmp/rakazo/control-token-1"
GATEWAY = f"--token-source={TARGETS} 0.0.0.0:6080"
TERMINAL_TOKEN = "s4ell_Token-0123456789abcdefghijkl"
TERMINAL_SOCKET = f"{SOCKETS}/terminal-1-{hashlib.sha256(HOLD_TOKEN.encode()).hexdigest()[:32]}"
TERMINAL_SERVER = "/tmp/rakazo/rakazo-terminal.py"
TERMINAL_TARGET = f"{TARGETS}/terminal-1"
TERMINAL_STAGED = "/tmp/rakazo/terminal-target-next-1"


def terminal_for(token: str) -> str:
    return open_terminal_script(token, TERMINAL_TOKEN)


ALL = (view_script, take_control_script, release_script, terminal_for)


def x11vnc_lines(script: str) -> list[str]:
    return [line for line in script.splitlines() if "nohup x11vnc" in line]


@pytest.mark.parametrize(
    "token", ["", "a" * 65, "two words", "tok'en", "a;reboot", "$(id)", "tök", "a\nb"]
)
@pytest.mark.parametrize("script", ALL)
def test_a_token_that_does_not_match_the_pattern_is_refused_before_any_script(
    script: Callable[[str], str], token: str
) -> None:
    with pytest.raises(TokenError, match="1 to 64"):
        script(token)


@pytest.mark.parametrize("script", ALL)
def test_every_script_is_bash_that_parses(script: Callable[[str], str]) -> None:
    checked = subprocess.run(
        ["bash", "-n", "-c", script(HOLD_TOKEN)], capture_output=True, check=False
    )

    assert checked.returncode == 0, checked.stderr.decode()


@pytest.mark.parametrize("script", ALL)
def test_every_process_pattern_is_anchored_so_it_cannot_match_the_script_itself(
    script: Callable[[str], str],
) -> None:
    patterns = re.findall(r"p(?:kill|grep) (?:-KILL )?-f ('[^']*'|\S+)", script(HOLD_TOKEN))

    assert patterns
    assert all(pattern.startswith("'^") for pattern in patterns), patterns


def test_the_view_is_a_view_only_vnc_on_its_own_socket_behind_the_view_target() -> None:
    script = view_script(HOLD_TOKEN)
    socket = f"{SOCKETS}/view-1-{HOLD_TOKEN}"

    (x11vnc,) = x11vnc_lines(script)
    assert "-display :1" in x11vnc
    assert "-viewonly" in x11vnc
    assert f"-unixsock {socket} " in x11vnc
    assert f"printf '%s: unix_socket:%s\\n' {HOLD_TOKEN} {socket} >" in script
    assert f"{TARGETS}/view-1" in script
    assert GATEWAY in script


def test_the_view_starts_vnc_only_when_its_socket_is_not_already_served() -> None:
    script = view_script(HOLD_TOKEN)

    guard = script.index(f"if [ ! -S {SOCKETS}/view-1-{HOLD_TOKEN} ] || ! pgrep -f")
    assert guard < script.index("nohup x11vnc")


def test_the_gateway_is_restarted_only_when_it_is_not_ours() -> None:
    script = view_script(HOLD_TOKEN)

    check = script.index("  if pgrep -f '^([^ ]*/)?python")
    assert (
        f"--token-source={TARGETS} +0.0.0.0:6080( |$)'" in script[check : script.index("\n", check)]
    )
    assert "then break; fi" in script[check : script.index("\n", check)]
    assert check < script.index("  pkill -f '^([^ ]*/)?python")
    assert check < script.index('nohup "$proxy"')


def test_the_screen_is_ready_only_when_our_gateway_owns_the_port() -> None:
    last = view_script(HOLD_TOKEN).rstrip().splitlines()[-1]

    assert last.startswith("pgrep -f '^([^ ]*/)?python")
    assert f"--token-source={TARGETS} +0.0.0.0:6080( |$)' >/dev/null && (echo >/dev/tcp/" in last


def test_control_is_a_vnc_that_takes_input_behind_the_control_target() -> None:
    script = take_control_script(HOLD_TOKEN)

    (x11vnc,) = x11vnc_lines(script)
    assert "-viewonly" not in x11vnc
    assert f"-unixsock {CONTROL_SOCKET} " in x11vnc
    assert f"printf %s {HOLD_TOKEN} >{TOKEN_FILE}" in script
    assert f"printf '%s: unix_socket:%s\\n' {HOLD_TOKEN} {CONTROL_SOCKET} >" in script
    assert f"{TARGETS}/control-1" in script
    assert GATEWAY in script


def test_taking_control_again_with_the_same_token_changes_nothing() -> None:
    first = take_control_script(HOLD_TOKEN).splitlines()

    assert first[1].startswith(f'[ -f {TOKEN_FILE} ] && [ "$(cat {TOKEN_FILE})" = {HOLD_TOKEN} ]')
    assert first[1].endswith("&& exit 0 || true")


def test_release_revokes_the_control_target_stops_its_vnc_and_forgets_the_token() -> None:
    script = release_script(HOLD_TOKEN)

    assert f'if [ -f {TOKEN_FILE} ] && [ "$(cat {TOKEN_FILE})" = {HOLD_TOKEN} ]; then' in script
    revoke = script.index(": >/tmp/rakazo/control-target-next-1")
    stop = script.index(f"pkill -f '^([^ ]*/)?x11vnc .* -unixsock {SOCKETS}/control-1-[^ ]+( |$)'")
    assert revoke < stop
    assert f"mv /tmp/rakazo/control-target-next-1 {TARGETS}/control-1" in script
    assert f"rm -f {TOKEN_FILE}" in script
    assert "x11vnc -display" not in script
    assert "view-1" not in script


def test_the_screen_url_is_rakazos_embed_page_on_the_published_port() -> None:
    url = urlsplit(screen_url(62480, HOLD_TOKEN, view_only=True))
    query = parse_qs(url.query)

    assert (url.scheme, url.netloc, url.path) == ("http", "127.0.0.1:62480", "/embed.html")
    assert query == {"path": [f"websockify?token={HOLD_TOKEN}"], "view_only": ["1"]}
    assert parse_qs(urlsplit(screen_url(1, HOLD_TOKEN, view_only=False)).query)["view_only"] == [
        "0"
    ]


def test_a_screen_url_with_a_bad_token_is_refused() -> None:
    with pytest.raises(TokenError):
        screen_url(62480, "a&view_only=0", view_only=True)


@pytest.mark.parametrize("token", ["", "a" * 65, "tok'en", "$(id)", "a\nb"])
def test_a_shell_token_that_does_not_match_the_pattern_is_refused(token: str) -> None:
    with pytest.raises(TokenError, match="1 to 64"):
        open_terminal_script(HOLD_TOKEN, token)


def test_the_shell_opens_only_while_this_token_holds_the_control_screen() -> None:
    script = open_terminal_script(HOLD_TOKEN, TERMINAL_TOKEN)

    check = script.index(f'[ -f {TOKEN_FILE} ] && [ "$(cat {TOKEN_FILE})" = {HOLD_TOKEN} ] ||')
    assert check < script.index("nohup python3")
    assert "exit 75" in script[check : script.index("\n", check)]


def test_the_shell_server_takes_its_program_on_stdin_and_serves_a_socket_named_for_the_hold() -> (
    None
):
    script = open_terminal_script(HOLD_TOKEN, TERMINAL_TOKEN)

    assert f"  cat >{TERMINAL_SERVER}.$$\n  mv {TERMINAL_SERVER}.$$ {TERMINAL_SERVER}\n" in script
    assert (
        f"HOME=/home/rakazo nohup python3 {TERMINAL_SERVER} {TERMINAL_SOCKET} /home/rakazo "
        "/tmp/rakazo/terminal-state-1 " in script
    )
    assert "import " not in script
    assert (
        f"printf '%s: unix_socket:%s\\n' {TERMINAL_TOKEN} {TERMINAL_SOCKET} >{TERMINAL_STAGED}"
        in script
    )
    assert script.index(f"mv {TERMINAL_STAGED} {TERMINAL_TARGET}") < script.index(GATEWAY)


def test_a_running_shell_server_is_reused_and_the_new_token_is_added_to_its_target() -> None:
    script = open_terminal_script(HOLD_TOKEN, TERMINAL_TOKEN)
    entry = f"printf '%s: unix_socket:%s\\n' {TERMINAL_TOKEN} {TERMINAL_SOCKET}"

    reuse = script.index(f"if [ -S {TERMINAL_SOCKET} ] && pgrep -f '^([^ ]*/)?python[0-9.]* ")
    otherwise = script.index("\nelse\n", reuse)
    appended = f"{{ cat {TERMINAL_TARGET} 2>/dev/null || true; {entry}; }} >{TERMINAL_STAGED}"
    assert appended in script[reuse:otherwise]
    assert "cat >" not in script[reuse:otherwise]


@pytest.mark.parametrize("script", [release_script, take_control_script])
def test_ending_or_renewing_a_hold_stops_the_shell_with_the_control_screen(
    script: Callable[[str], str],
) -> None:
    text = script(HOLD_TOKEN)

    revoke = text.index(f": >{TERMINAL_STAGED}; mv {TERMINAL_STAGED} {TERMINAL_TARGET}")
    server = f"{TERMINAL_SERVER} {SOCKETS}/terminal-1-[^ ]+"
    kill = text.index(f"pkill -f '^([^ ]*/)?python[0-9.]* {server}")
    assert revoke < kill
    assert f"rm -rf {SOCKETS}/terminal-1-* /tmp/rakazo/terminal-state-1" in text


def test_the_shell_url_is_the_gateway_socket_for_its_token() -> None:
    url = terminal_url(62480, TERMINAL_TOKEN)

    assert url == f"http://127.0.0.1:62480/websockify?token={TERMINAL_TOKEN}"
    with pytest.raises(TokenError):
        terminal_url(62480, "a&b")
