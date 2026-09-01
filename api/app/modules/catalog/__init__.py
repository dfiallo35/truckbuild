"""The catalog: platforms, their option groups and options, and the pricing and compatibility
rules over them. Everything the marketing site and the configurator read.

The module's ``APIRouter`` is exported here because that is all ``app.main`` needs of it. Another
module may reach into ``domain`` and ``application``; ``presentation`` and ``infrastructure`` are
this module's own adapters and are off limits from outside -- see
Stage 8 of the archived development plan (Notion).
"""

from app.modules.catalog.presentation.routes import router

__all__ = ["router"]
