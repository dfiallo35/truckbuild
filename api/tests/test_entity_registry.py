"""Every module's tables must reach ``SQLModel.metadata`` by the time Alembic looks.

Stage 8 split one eager ``models/__init__.py`` into one table package per module, which
introduced a way to forget one: a package that ``alembic/env.py`` never imports is a package
whose tables autogenerate cannot see, and the migration it then writes drops them without
saying so. That mistake is invisible in review and expensive in production, so it is checked
here instead -- at the moment it is made rather than months later in a migration diff.

Two halves, because there are two ways to lose a table: a module missing from ``env.py``'s
import list, and a submodule missing from its package's ``__init__``.

Since Stage 11 both modules keep their tables in the same place -- ``infrastructure/postgres/``,
with the entities they store as pure pydantic in ``domain/models.py``. The discovery below still
looks in both places, because it follows the tables rather than a layout, which is what it was
always really checking.
"""

import ast
import subprocess
import sys
from pathlib import Path

from tests.conftest import API_ROOT

MODULES_ROOT = API_ROOT / "app" / "modules"

# Discovered by following the tables themselves rather than a list someone has to remember to
# extend -- and by globbing for the file rather than for the directory that holds it, so a
# leftover `__pycache__` from the pre-Stage-11 layout cannot make this report a module that no
# longer exists.
TABLE_MODULES = sorted(
    f"app.modules.{path.parents[2].name}.infrastructure.postgres.tables"
    for path in MODULES_ROOT.glob("*/infrastructure/postgres/tables.py")
)


def test_table_modules_are_discoverable() -> None:
    """A guard on the guard: if the layout moves, the two tests below would pass vacuously."""
    assert TABLE_MODULES == [
        "app.modules.catalog.infrastructure.postgres.tables",
        "app.modules.quotes.infrastructure.postgres.tables",
    ]


def test_alembic_env_imports_every_table_module() -> None:
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
    assert imported == TABLE_MODULES


# Run in a fresh interpreter: in-process, pytest's own collection has already imported half the
# app, and a table registered by some other test's import would mask exactly what this checks.
_PROBE = """
import importlib, pkgutil, sys
from sqlmodel import SQLModel

names = {names!r}
for name in names:
    importlib.import_module(name)

# What the imports themselves registered -- i.e. what Alembic gets.
registered = set(SQLModel.metadata.tables)

missing = {{}}
for name in names:
    module = sys.modules[name]
    # A package hides its tables one level down; a plain module carries them itself.
    siblings = (
        [f"{{name}}.{{info.name}}" for info in pkgutil.iter_modules(module.__path__)]
        if hasattr(module, "__path__")
        else [name]
    )
    for sibling in siblings:
        submodule = importlib.import_module(sibling)
        for obj in vars(submodule).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, SQLModel)
                and obj.__module__ == submodule.__name__
                and hasattr(obj, "__table__")
                and obj.__tablename__ not in registered
            ):
                missing[obj.__tablename__] = submodule.__name__

if missing:
    raise SystemExit(f"unregistered: {{missing}}")
"""


def test_every_table_class_is_registered_by_its_module() -> None:
    """Import each table module the way ``env.py`` does, then walk what sits beside it. A
    table found on disk but absent from the metadata is one whose ``__init__`` forgot it."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE.format(names=TABLE_MODULES)],
        cwd=Path(API_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "these tables exist on disk but are not on SQLModel.metadata after importing their "
        f"own module, so autogenerate would drop them:\n{result.stdout}{result.stderr}"
    )


def test_every_table_keeps_the_name_the_first_migration_created() -> None:
    """``__tablename__`` is pinned on every table because SQLModel derives it from the class
    name: renaming ``Platform`` to ``PlatformTable`` in Stage 10, and ``Quote`` to ``QuoteTable``
    in Stage 11, would otherwise have renamed seven tables -- which autogenerate writes as
    ``drop_table`` + ``create_table``, i.e. as deleting every stored lead."""
    from app.modules.catalog.infrastructure.postgres import tables as catalog_tables
    from app.modules.quotes.infrastructure.postgres import tables as quote_tables

    assert {
        catalog_tables.PlatformTable.__tablename__,
        catalog_tables.OptionGroupTable.__tablename__,
        catalog_tables.OptionTable.__tablename__,
        catalog_tables.OptionRuleTable.__tablename__,
        catalog_tables.AssetTable.__tablename__,
        quote_tables.QuoteTable.__tablename__,
        quote_tables.QuoteLineTable.__tablename__,
    } == {"platform", "optiongroup", "option", "optionrule", "asset", "quote", "quoteline"}
