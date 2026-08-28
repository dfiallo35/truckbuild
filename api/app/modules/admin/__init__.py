"""Staff-only reads over the leads ``quotes`` stores and the platforms ``catalog`` owns, plus a
manual cache revalidation trigger.

Owns no entities and no tables, so it carries no ``domain`` and no ``infrastructure``: a module
carries only the layers it needs.
"""

from app.modules.admin.presentation.router import router

__all__ = ["router"]
