"""Lead submission: a configured build or a general enquiry, priced by the server and stored.

Depends on ``catalog`` -- pricing a submission means reading a platform and applying the
catalog's own pricing and rules -- and on nothing else. See ``app.modules.catalog`` for the
facade rule that governs how.

The module's ``APIRouter`` is exported here because that is all ``app.main`` needs of it. Another
module may reach into ``domain`` and ``application``; ``presentation`` and ``infrastructure`` are
this module's own adapters and are off limits from outside.
"""

from app.modules.quotes.presentation.routes import router

__all__ = ["router"]
