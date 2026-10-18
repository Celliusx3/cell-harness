"""What the computer runs for a bot's command: write its job, run it detached, and look at it."""

from __future__ import annotations

RUNNER_NAME = "shell-job"

RUNNER_SCRIPT = (
    'cd "$2" 2>"$1/out" && sh "$1/cmd" <"$1/in" >"$1/out" 2>&1; '
    'echo $? >"$1/exit.tmp"; mv "$1/exit.tmp" "$1/exit"'
)

IS_RUNNING_DEFINITION = "\n".join(
    [
        "def is_running(folder):",
        "    mark, me = folder.encode() + b'\\0', str(os.getpid())",
        "    for pid in os.listdir('/proc'):",
        "        if not pid.isdigit() or pid == me:",
        "            continue",
        "        try:",
        "            with open('/proc/' + pid + '/cmdline', 'rb') as cmdline:",
        "                if mark in cmdline.read():",
        "                    return True",
        "        except OSError:",
        "            continue",
        "    return False",
    ]
)

WRITE_SCRIPT = "\n".join(
    [
        "import json, os, sys, time",
        "folder = sys.argv[1]",
        "job = json.loads(sys.stdin.buffer.read().decode('utf-8'))",
        "os.makedirs(folder, mode=0o700)",
        "for name, text in (('cmd', job['command']), ('in', job['stdin'])):",
        "    with open(os.path.join(folder, name), 'w', encoding='utf-8') as written:",
        "        written.write(text)",
        "with open(os.path.join(folder, 'started'), 'w') as written:",
        "    written.write(repr(time.time()))",
    ]
)

LOOK_SCRIPT = "\n".join(
    [
        "import json, os, shutil, sys, time",
        IS_RUNNING_DEFINITION,
        "folder, most_bytes = sys.argv[1], int(sys.argv[2])",
        "def tail():",
        "    try:",
        "        with open(os.path.join(folder, 'out'), 'rb') as out:",
        "            out.seek(max(0, os.fstat(out.fileno()).st_size - most_bytes))",
        "            return out.read().decode('utf-8', 'replace')",
        "    except FileNotFoundError:",
        "        return ''",
        "def started():",
        "    with open(os.path.join(folder, 'started')) as written:",
        "        return float(written.read())",
        "alive = is_running(folder)",
        "finished = os.path.join(folder, 'exit')",
        "if os.path.exists(finished):",
        "    with open(finished) as written:",
        "        code = int(written.read())",
        "    seconds = os.stat(finished).st_mtime - started()",
        "    seen = {'state': 'done', 'exit_code': code, 'seconds': seconds, 'output': tail()}",
        "    shutil.rmtree(folder)",
        "elif alive:",
        "    seen = {'state': 'running', 'seconds': time.time() - started(), 'output': tail()}",
        "else:",
        "    shutil.rmtree(folder, ignore_errors=True)",
        "    seen = {'state': 'none'}",
        "print(json.dumps(seen))",
    ]
)

RUNNING_JOBS_SCRIPT = "\n".join(
    [
        "import os, sys",
        IS_RUNNING_DEFINITION,
        "root = sys.argv[1]",
        "names = sorted(os.listdir(root)) if os.path.isdir(root) else []",
        "for name in names:",
        "    folder = os.path.join(root, name)",
        "    if is_running(folder) and not os.path.exists(os.path.join(folder, 'exit')):",
        "        print(name)",
    ]
)
