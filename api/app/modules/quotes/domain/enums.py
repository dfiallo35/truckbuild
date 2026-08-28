from enum import StrEnum


class QuoteKind(StrEnum):
    """A lead is either a configured build or a general enquiry from /contact. Both land in the
    same table so sales reads one list and one series of reference numbers."""

    build = "build"
    enquiry = "enquiry"
