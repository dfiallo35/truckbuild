"""Every port a module declares is bound at the composition root.

``quotes`` and ``admin`` both read the catalog, and neither may name ``catalog``'s adapters (the
facade rule, CLAUDE.md). Each therefore declares what it needs as a dependency that raises
``NotImplementedError``, and ``app/main.py`` binds it to the provider ``catalog`` supplies.

The failure this guards is the quiet one: an unbound port is a 500 on exactly one endpoint, found
by whoever calls it next. The ports are discovered from the source rather than listed here, so a
port added in Stage 11 or 12 and never bound fails this test on the day it is written.
"""

import ast
import importlib

from tests.conftest import API_ROOT

MODULES_ROOT = API_ROOT / "app" / "modules"


def _declared_ports() -> dict[str, list[str]]:
    """Module-level functions under a ``presentation/`` whose whole body is
    ``raise NotImplementedError`` -- the shape of a port awaiting a binding."""
    found: dict[str, list[str]] = {}
    for path in sorted(MODULES_ROOT.glob("*/presentation/*.py")):
        tree = ast.parse(path.read_text())
        names = [
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(statement, ast.Raise) and "NotImplementedError" in ast.dump(statement)
                for statement in node.body
            )
        ]
        if names:
            module = f"app.modules.{path.parents[1].name}.presentation.{path.stem}"
            found[module] = names
    return found


def test_the_ports_are_where_this_test_thinks_they_are() -> None:
    """A guard on the guard: an empty discovery would make the test below pass vacuously."""
    assert _declared_ports() == {
        "app.modules.admin.presentation.dependencies": [
            "get_platform_repository",
            "get_cache_invalidator",
            "get_quote_repository",
        ],
        "app.modules.catalog.presentation.catalog_api": ["get_catalog_service"],
        "app.modules.quotes.presentation.quotes_api": [
            "get_quote_service",
            "get_mailer",
            "get_platform_repository",
        ],
    }


def test_every_declared_port_is_bound_in_main() -> None:
    from app.main import app

    unbound = [
        f"{module}.{name}"
        for module, names in _declared_ports().items()
        for name in names
        if getattr(importlib.import_module(module), name) not in app.dependency_overrides
    ]
    assert not unbound, f"declared but never bound in app/main.py: {unbound}"


def test_an_unbound_port_fails_loudly() -> None:
    """The placeholder raises rather than returning ``None``: a port that answered with nothing
    would surface as an empty catalog, which reads like missing data rather than missing wiring."""
    import pytest

    from app.modules.quotes.presentation.quotes_api import get_platform_repository

    with pytest.raises(NotImplementedError):
        get_platform_repository()
