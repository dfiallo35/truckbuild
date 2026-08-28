"""Staff-only reads over the leads ``quotes`` stores and the platforms ``catalog`` owns, plus a
manual cache revalidation trigger.

Owns no entities and no tables, so it carries no ``infrastructure``: a module carries only the
layers it needs. ``domain/`` exists but is empty -- it gives the "Domain forbids persistence" and
"Domain isolation" contracts in ``pyproject.toml`` something to check across every module rather
than three of four.
"""

from app.modules.admin.presentation.routes import router

__all__ = ["router"]
