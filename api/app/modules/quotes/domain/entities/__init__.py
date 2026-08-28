"""The quotes module's SQLModel tables. Imported eagerly for the same two reasons as the
catalog's -- see ``app.modules.catalog.domain.entities``."""

from app.modules.quotes.domain.entities.quote import Quote, QuoteLine

__all__ = ["Quote", "QuoteLine"]
