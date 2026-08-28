"""Lead submission: a configured build or a general enquiry, priced by the server and stored.

Depends on ``catalog`` -- pricing a submission means reading a platform and applying the
catalog's own pricing and rules -- and on nothing else. See ``app.modules.catalog`` for the
facade rule that governs how.
"""

from app.modules.quotes.presentation.router import router

__all__ = ["router"]
