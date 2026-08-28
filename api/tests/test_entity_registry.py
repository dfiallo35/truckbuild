"""Every module's tables must reach ``SQLModel.metadata`` by the time Alembic looks.

Stage 8 split one eager ``models/__init__.py`` into one entity package per module, which
introduced a way to forget one: a package that ``alembic/env.py`` never imports is a package
whose tables autogenerate cannot see, and the migration it then writes drops them without
saying so. That mistake is invisible in review and expensive in production, so it is checked
here instead -- at the moment it is made rather than months later in a migration diff.

Two halves, because there are two ways to lose a table: a module missing from ``env.py``'s
import list, and a submodule missing from its package's ``__init__``.
"""

import ast
import subprocess
import sys
from pathlib import Path

from tests.conftest import API_ROOT

ENTITY_PACKAGES = sorted(
    f"app.modules.{path.parent.parent.name}.domain.entities"
    for path in (API_ROOT / "app" / "modules").glob("*/domain/entities")
)


def test_entity_packages_are_discoverable() -> None:
    """A guard on the guard: if the layout moves, the two tests below would pass vacuously."""
    assert ENTITY_PACKAGES == [
        "app.modules.catalog.domain.entities",
        "app.modules.quotes.domain.entities",
    ]


def test_alembic_env_imports_every_entity_package() -> None:
    """``alembic/env.py`` is where a new module gets forgotten -- everything else about it
    keeps working, and only the next autogenerate reveals the omission."""
    tree = ast.parse((API_ROOT / "alembic" / "env.py").read_text())
    imported = sorted(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.name.startswith("app.modules.")
    )
    assert imported == ENTITY_PACKAGES


# Run in a fresh interpreter: in-process, pytest's own collection has already imported half the
# app, and a table registered by some other test's import would mask exactly what this checks.
_PROBE = """
import importlib, pkgutil, sys
from sqlmodel import SQLModel

packages = {packages!r}
for name in packages:
    importlib.import_module(name)

# What the packages themselves registered -- i.e. what Alembic gets.
registered = set(SQLModel.metadata.tables)

missing = {{}}
for name in packages:
    package = sys.modules[name]
    for info in pkgutil.iter_modules(package.__path__):
        module = importlib.import_module(f"{{name}}.{{info.name}}")
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, SQLModel)
                and obj.__module__ == module.__name__
                and hasattr(obj, "__table__")
                and obj.__tablename__ not in registered
            ):
                missing[obj.__tablename__] = module.__name__

if missing:
    raise SystemExit(f"unregistered: {{missing}}")
"""


def test_every_entity_class_is_registered_by_its_package() -> None:
    """Import each entity package the way ``env.py`` does, then walk the files beside it. A
    table found on disk but absent from the metadata is one whose ``__init__`` forgot it."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(packages=ENTITY_PACKAGES)],
        cwd=Path(API_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "these tables exist on disk but are not on SQLModel.metadata after importing their "
        f"own package, so autogenerate would drop them:\n{result.stdout}{result.stderr}"
    )
