"""The live screen and shell bash scripts, adapted from Rakazo's desktop-runtime.ts (see NOTICE)."""

from __future__ import annotations

import hashlib
import re
import shlex
from typing import Literal
from urllib.parse import urlencode

from computer.machine import DISPLAY, GATEWAY_PORT, HOME
from computer.models import ScreenMode

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")
DISPLAY_NUMBER = DISPLAY.removeprefix(":")
RAKAZO_DIR = "/tmp/rakazo"
TARGETS = f"{RAKAZO_DIR}/desktop-targets"
SOCKETS = f"{RAKAZO_DIR}/sockets"
HOLD_TOKEN_FILE = f"{RAKAZO_DIR}/control-token-{DISPLAY_NUMBER}"
TERMINAL_SERVER = f"{RAKAZO_DIR}/rakazo-terminal.py"
TERMINAL_STATE = f"{RAKAZO_DIR}/terminal-state-{DISPLAY_NUMBER}"
WEBSOCKIFY_PATTERN = "^([^ ]*/)?python[0-9.]* +(-m +websockify|[^ ]*websockify[^ ]*) +.*"
GATEWAY_ATTEMPTS = 5
GATEWAY_ANSWERS = f"(echo >/dev/tcp/127.0.0.1/{GATEWAY_PORT}) >/dev/null 2>&1"
PROXY_ENVIRONMENT = "\n".join(
    [
        "if command -v websockify >/dev/null 2>&1; then proxy=$(command -v websockify); "
        "elif [ -x /opt/noVNC/utils/websockify/run ]; then proxy=/opt/noVNC/utils/websockify/run; "
        'else echo "websockify is required" >&2; exit 1; fi',
        "if [ -d /usr/share/novnc ]; then web=/usr/share/novnc; "
        "elif [ -d /opt/noVNC ]; then web=/opt/noVNC; "
        'else echo "noVNC is required" >&2; exit 1; fi',
    ]
)

TargetKind = Literal["view", "control", "terminal"]


class TokenError(ValueError):
    """A token this server will not put in a script or a link."""


def checked_token(token: str) -> str:
    if TOKEN_PATTERN.fullmatch(token) is None:
        raise TokenError("a screen token is 1 to 64 letters, digits, '_' or '-'")
    return token


def hold_key(token: str) -> str:
    """What names the hold's sockets."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]


def screen_url(port: int, token: str, *, view_only: bool) -> str:
    """Rakazo's noVNC page on the published gateway port, opening the screen this token names."""
    query = urlencode(
        {"path": f"websockify?token={checked_token(token)}", "view_only": "1" if view_only else "0"}
    )
    return f"http://127.0.0.1:{port}/embed.html?{query}"


def terminal_url(port: int, token: str) -> str:
    """The gateway's socket for the shell this token names."""
    return f"http://127.0.0.1:{port}/websockify?token={checked_token(token)}"


def x11vnc_pattern(socket: str) -> str:
    return shlex.quote(f"^([^ ]*/)?x11vnc .* -unixsock {socket}( |$)")


def x11vnc_script(socket: str, *, view_only: bool, log: str) -> str:
    viewonly = " -viewonly" if view_only else ""
    return (
        f"nohup x11vnc -display {DISPLAY} -forever -shared{viewonly} -nopw -rfbport 0 "
        f"-unixsock {socket} -xkb -ncache 0 8>&- 9>&- </dev/null >{log} 2>&1 &"
    )


def publish_target_script(kind: TargetKind, token: str, socket: str) -> str:
    """The gateway's token line for this screen, swapped in whole so a reader never sees half."""
    staged = f"{RAKAZO_DIR}/{kind}-target-next-{DISPLAY_NUMBER}"
    return "\n".join(
        [
            f"for i in $(seq 1 50); do [ -S {socket} ] && break; sleep 0.1; done",
            f"[ -S {socket} ] || exit 1",
            f"printf '%s: unix_socket:%s\\n' {token} {socket} >{staged}",
            f"mv {staged} {TARGETS}/{kind}-{DISPLAY_NUMBER}",
        ]
    )


def revoke_target_script(kind: TargetKind) -> str:
    """The target file emptied, not removed: the gateway may be reading the directory."""
    staged = f"{RAKAZO_DIR}/{kind}-target-next-{DISPLAY_NUMBER}"
    return f"mkdir -p {TARGETS}; : >{staged}; mv {staged} {TARGETS}/{kind}-{DISPLAY_NUMBER}"


def stop_vnc_script(kind: ScreenMode) -> str:
    prefix = f"{SOCKETS}/{kind}-{DISPLAY_NUMBER}-"
    pattern = x11vnc_pattern(f"{prefix}[^ ]+")
    return "\n".join(
        [
            f"pkill -f {pattern} || true",
            "sleep 0.1",
            f"pkill -KILL -f {pattern} || true",
            f"for i in $(seq 1 10); do pgrep -f {pattern} >/dev/null || break; sleep 0.1; done",
            f"if pgrep -f {pattern} >/dev/null; then "
            "echo 'computer screen transport failed to stop' >&2; exit 1; fi",
            f"rm -f {prefix}*",
        ]
    )


def gateway_script() -> str:
    """websockify serving every target in the directory; started only when it is not already."""
    on_port = shlex.quote(f"{WEBSOCKIFY_PATTERN}[ :]{GATEWAY_PORT}( |$)")
    ours = shlex.quote(f"{WEBSOCKIFY_PATTERN}--token-source={TARGETS} +0.0.0.0:{GATEWAY_PORT}( |$)")
    lock = f"{RAKAZO_DIR}/gateway-{GATEWAY_PORT}.lock"
    return "\n".join(
        [
            PROXY_ENVIRONMENT,
            f"mkdir -p {TARGETS}",
            f"exec 10>{lock}; flock -w 120 10",
            f"for attempt in $(seq 1 {GATEWAY_ATTEMPTS}); do",
            f"  if pgrep -f {ours} >/dev/null && {GATEWAY_ANSWERS}; then break; fi",
            f"  pkill -f {on_port} || true",
            f"  for i in $(seq 1 20); do if ! {GATEWAY_ANSWERS}; then break; fi; sleep 0.1; done",
            '  nohup "$proxy" --heartbeat=30 --web="$web" --token-plugin=TokenFile '
            f"--token-source={TARGETS} 0.0.0.0:{GATEWAY_PORT} 8>&- 9>&- 10>&- </dev/null "
            f">{RAKAZO_DIR}/gateway-{GATEWAY_PORT}.log 2>&1 &",
            f"  for i in $(seq 1 50); do {GATEWAY_ANSWERS} && break; sleep 0.1; done",
            "  sleep 0.5",
            "done",
            "flock -u 10; exec 10>&-",
            f"pgrep -f {ours} >/dev/null && {GATEWAY_ANSWERS}",
        ]
    )


def view_script(token: str) -> str:
    """A view-only VNC of the display behind this token; running it again changes nothing."""
    token = checked_token(token)
    socket = f"{SOCKETS}/view-{DISPLAY_NUMBER}-{token}"
    return "\n".join(
        [
            "set -eu",
            f"for i in $(seq 1 100); do xdpyinfo -display {DISPLAY} >/dev/null 2>&1 && break; "
            "sleep 0.1; done",
            f"xdpyinfo -display {DISPLAY} >/dev/null 2>&1 || exit 1",
            f"mkdir -p {TARGETS} {SOCKETS}",
            f"if [ ! -S {socket} ] || ! pgrep -f {x11vnc_pattern(socket)} >/dev/null; then",
            stop_vnc_script("view"),
            "  "
            + x11vnc_script(
                socket, view_only=True, log=f"{RAKAZO_DIR}/x11vnc-view-{DISPLAY_NUMBER}.log"
            ),
            "fi",
            publish_target_script("view", token, socket),
            gateway_script(),
        ]
    )


def terminal_server_pattern(socket: str) -> str:
    return shlex.quote(f"^([^ ]*/)?python[0-9.]* {TERMINAL_SERVER} {socket}( |$)")


def stop_terminal_script() -> str:
    """Killing the server closes every relayed shell; each shell then gets SIGHUP."""
    prefix = f"{SOCKETS}/terminal-{DISPLAY_NUMBER}-"
    pattern = terminal_server_pattern(f"{prefix}[^ ]+")
    return "\n".join(
        [
            revoke_target_script("terminal"),
            f"pkill -f {pattern} || true",
            f"for i in $(seq 1 10); do pgrep -f {pattern} >/dev/null || break; sleep 0.1; done",
            f"pkill -KILL -f {pattern} || true",
            f"rm -rf {prefix}* {TERMINAL_STATE}",
        ]
    )


def stop_control_script() -> str:
    """The control screen and the shell that belongs to its hold, closed together."""
    return "\n".join(
        [
            revoke_target_script("control"),
            stop_vnc_script("control"),
            stop_terminal_script(),
            f"rm -f {HOLD_TOKEN_FILE}",
        ]
    )


def take_control_script(token: str) -> str:
    """A VNC that takes the person's input, behind this token; the same token again is a no-op."""
    token = checked_token(token)
    socket = f"{SOCKETS}/control-{DISPLAY_NUMBER}-{hold_key(token)}"
    held = f'[ -f {HOLD_TOKEN_FILE} ] && [ "$(cat {HOLD_TOKEN_FILE})" = {token} ]'
    return "\n".join(
        [
            "set -eu",
            f"{held} && [ -S {socket} ] && pgrep -f {x11vnc_pattern(socket)} >/dev/null "
            f"&& {GATEWAY_ANSWERS} && exit 0 || true",
            stop_control_script(),
            f"mkdir -p {TARGETS} {SOCKETS}",
            f"printf %s {token} >{HOLD_TOKEN_FILE}",
            x11vnc_script(
                socket, view_only=False, log=f"{RAKAZO_DIR}/x11vnc-control-{DISPLAY_NUMBER}.log"
            ),
            publish_target_script("control", token, socket),
            gateway_script(),
        ]
    )


def release_script(token: str) -> str:
    """The control screen closed, if this token still holds it: target, VNC and token file."""
    token = checked_token(token)
    return "\n".join(
        [
            "set -eu",
            f'if [ -f {HOLD_TOKEN_FILE} ] && [ "$(cat {HOLD_TOKEN_FILE})" = {token} ]; then',
            stop_control_script(),
            "printf 'RAKAZO_CONTROL_RELEASED\\n'",
            "fi",
        ]
    )


def open_terminal_script(hold_token: str, terminal_token: str) -> str:
    """A shell behind terminal_token for this hold; the server's program is on stdin."""
    hold_token, terminal_token = checked_token(hold_token), checked_token(terminal_token)
    socket = f"{SOCKETS}/terminal-{DISPLAY_NUMBER}-{hold_key(hold_token)}"
    target = f"{TARGETS}/terminal-{DISPLAY_NUMBER}"
    staged = f"{RAKAZO_DIR}/terminal-target-next-{DISPLAY_NUMBER}"
    entry = f"printf '%s: unix_socket:%s\\n' {terminal_token} {socket}"
    held = f'[ -f {HOLD_TOKEN_FILE} ] && [ "$(cat {HOLD_TOKEN_FILE})" = {hold_token} ]'
    return "\n".join(
        [
            "set -eu",
            f"{held} || {{ echo 'the control screen is not open' >&2; exit 75; }}",
            f"if [ -S {socket} ] && pgrep -f {terminal_server_pattern(socket)} >/dev/null; then",
            f"  {{ cat {target} 2>/dev/null || true; {entry}; }} >{staged}",
            "else",
            stop_terminal_script(),
            f"  mkdir -p {TARGETS} {SOCKETS}",
            f"  cat >{TERMINAL_SERVER}.$$",
            f"  mv {TERMINAL_SERVER}.$$ {TERMINAL_SERVER}",
            f"  HOME={HOME} nohup python3 {TERMINAL_SERVER} {socket} {HOME} {TERMINAL_STATE} "
            f"8>&- 9>&- </dev/null >{RAKAZO_DIR}/terminal-{DISPLAY_NUMBER}.log 2>&1 &",
            f"  for i in $(seq 1 50); do [ -S {socket} ] && break; sleep 0.1; done",
            f"  [ -S {socket} ] || exit 1",
            f"  {entry} >{staged}",
            "fi",
            f"mv {staged} {target}",
            gateway_script(),
        ]
    )
