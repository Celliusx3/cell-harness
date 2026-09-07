"""The dependency rule, enforced at file level.

The folders are gone; the rule they were there to express is not. What a
conversation *is* must not come to depend on where it happens to be stored —
otherwise swapping JSONL for SQLite stops being a one-line change and the seam
was decorative.

    repositories/jsonl ─┐
    service ────────────┼─→  models · log · derive · repair
    repository ─────────┘

Arrows never point the other way.

`harness/sandbox` has the same shape as a rule with no arrows at all: it runs a
script and calls back, and the moment it learns what a `ToolOutcome` is, the next
thing that wants a sandbox has to bring the tool domain with it.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

HARNESS = pathlib.Path(__file__).resolve().parents[2] / "harness"
SESSION = HARNESS / "session"
SANDBOX = HARNESS / "sandbox"

# Modules that describe a conversation. None may know about storage.
PURE = ("models", "log", "derive", "repair")
# Modules that store one, or decide when to. `repositories` covers every backend
# in that folder, so a new one is caught without editing this list.
STORAGE = ("repository", "repositories", "service")


def session_imports(name: str) -> list[str]:
    """Every `harness.session.*` module that `name` imports from.

    Returns the first path segment, so `repositories.jsonl` reports as
    `repositories` — one entry covers every backend in that folder.
    """
    tree = ast.parse((SESSION / f"{name}.py").read_text())
    modules = [
        node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
    ]
    prefix = "harness.session."
    return [m.removeprefix(prefix).split(".")[0] for m in modules if m.startswith(prefix)]


@pytest.mark.parametrize("name", PURE)
def test_a_pure_module_knows_nothing_about_storage(name: str) -> None:
    for imported in session_imports(name):
        assert imported not in STORAGE, (
            f"{name}.py imports {imported!r}. What a conversation is must not "
            f"depend on where it is kept — that is what keeps the backend swappable."
        )


@pytest.mark.parametrize("name", PURE)
def test_a_pure_module_does_no_io(name: str) -> None:
    """A module that opens a file here would mean the log's meaning depends on
    the medium it happens to sit on."""
    forbidden = {"os", "pathlib", "httpx", "sqlite3", "socket", "aiofiles"}
    tree = ast.parse((SESSION / f"{name}.py").read_text())
    for node in ast.walk(tree):
        names = (
            [a.name for a in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        for imported in names:
            assert imported.split(".")[0] not in forbidden, (
                f"{name}.py imports {imported!r}. These modules do no I/O."
            )


def test_the_service_depends_on_the_port_not_the_backend() -> None:
    """The swap in one assertion: if `service.py` ever names a concrete
    repository, changing backends stops being a change at the composition root.
    """
    assert "repositories" not in session_imports("service")
    assert "repository" in session_imports("service")


def test_every_named_module_exists() -> None:
    """A guard on the guard: a renamed file would make the checks above pass by
    describing modules nobody has."""
    for name in PURE + STORAGE:
        target = SESSION / f"{name}.py"
        assert target.exists() or (SESSION / name).is_dir(), f"session/{name} is missing"


def test_at_least_one_backend_exists() -> None:
    """`repositories/` with nothing in it would mean the port has no
    implementation and every swap claim is untested."""
    backends = [p for p in (SESSION / "repositories").glob("*.py") if p.stem != "__init__"]
    assert backends, "session/repositories/ holds no backend"


# ── the sandbox knows nothing ─────────────────────────────────────────────────


def test_the_sandbox_imports_nothing_from_the_harness() -> None:
    """It takes code, some names, and a callback. Anything more — a `ToolOutcome`,
    a registry, a session — makes it code mode's private runtime rather than a
    sandbox, and the coupling grows back the first time someone finds it handy.
    """
    leaks: list[str] = []
    for path in sorted(SANDBOX.rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            imported = (
                [node.module]
                if isinstance(node, ast.ImportFrom) and node.module
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            leaks += [
                f"{path.name} imports {m}"
                for m in imported
                if m.startswith("harness.") and not m.startswith("harness.sandbox")
            ]

    assert leaks == [], leaks
