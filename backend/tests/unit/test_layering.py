"""The dependency rule, enforced at file level."""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

HARNESS = pathlib.Path(__file__).resolve().parents[2] / "harness"
SESSION = HARNESS / "session"
SANDBOX = HARNESS / "sandbox"

PURE = ("models", "log", "derive", "repair")
CIRCULAR_IMPORT_RISK = ("harness.session.models", "harness.tools.client", "harness.skills.tool")
STORAGE = ("repository", "repositories", "service")
OUTER_LAYERS = ("repository", "service", "router")
IO_MODULES = frozenset(
    (
        "os",
        "httpx",
        "sqlite3",
        "socket",
        "aiofiles",
        "tempfile",
        "shutil",
        "subprocess",
        "zipfile",
        "fastapi",
    )
)
DOMAIN_MODULES = sorted(HARNESS.glob("*/domain/**/*.py"))


def session_imports(name: str) -> list[str]:
    """Every `harness.session.*` module that `name` imports from."""
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
    assert "repositories" not in session_imports("service")
    assert "repository" in session_imports("service")


def test_every_named_module_exists() -> None:
    for name in PURE + STORAGE:
        target = SESSION / f"{name}.py"
        assert target.exists() or (SESSION / name).is_dir(), f"session/{name} is missing"


def test_at_least_one_backend_exists() -> None:
    backends = [p for p in (SESSION / "repositories").glob("*.py") if p.stem != "__init__"]
    assert backends, "session/repositories/ holds no backend"


def test_the_sandbox_imports_nothing_from_the_harness() -> None:
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


def test_the_prompts_import_nothing() -> None:
    tree = ast.parse((HARNESS / "prompts.py").read_text())
    imported = [
        node.module or "" if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    ]

    assert imported == ["__future__"], imported


def test_no_package_imports_another_package_s_private_module() -> None:
    leaks: list[str] = []
    for path in sorted(HARNESS.rglob("*.py")):
        package = path.relative_to(HARNESS).parts[0]
        for node in ast.walk(ast.parse(path.read_text())):
            imported = (
                [f"{node.module}.{alias.name}" for alias in node.names]
                if isinstance(node, ast.ImportFrom) and node.module
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            leaks += [
                f"{path.relative_to(HARNESS)} imports {m}"
                for m in imported
                if m.startswith("harness.")
                and m.split(".")[1] != package
                and any(part.startswith("_") for part in m.split(".")[2:])
            ]

    assert leaks == [], leaks


@pytest.mark.parametrize("module", CIRCULAR_IMPORT_RISK)
def test_a_module_that_could_import_circularly_loads_on_its_own(module: str) -> None:
    run = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        cwd=HARNESS.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr


def imported_names(path: pathlib.Path) -> list[str]:
    """Every module `path` imports, and every `module.name` it imports from one."""
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names += [node.module] + [f"{node.module}.{alias.name}" for alias in node.names]
    return names


def test_every_layered_package_is_checked() -> None:
    assert DOMAIN_MODULES, "no harness/<package>/domain/ module was found, so nothing is checked"


@pytest.mark.parametrize("path", DOMAIN_MODULES, ids=lambda p: str(p.relative_to(HARNESS)))
def test_a_domain_module_imports_none_of_its_package_s_outer_layers(path: pathlib.Path) -> None:
    package = path.relative_to(HARNESS).parts[0]
    outer = {f"harness.{package}.{layer}" for layer in OUTER_LAYERS}
    leaks = sorted({m for m in imported_names(path) if ".".join(m.split(".")[:3]) in outer})

    assert leaks == [], (
        f"{path.relative_to(HARNESS)} imports {leaks}. The domain is the data and the rules "
        f"that only compute; storage, the code that acts and the routes depend on it, "
        f"never the reverse."
    )


@pytest.mark.parametrize("path", DOMAIN_MODULES, ids=lambda p: str(p.relative_to(HARNESS)))
def test_a_domain_module_does_no_io(path: pathlib.Path) -> None:
    leaks = sorted({m for m in imported_names(path) if m.split(".")[0] in IO_MODULES})

    assert leaks == [], (
        f"{path.relative_to(HARNESS)} imports {leaks}. A domain module only computes; "
        f"input and output belong in the repository or the service."
    )
