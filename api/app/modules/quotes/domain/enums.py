from enum import StrEnum


class QuoteKind(StrEnum):
    """A lead is either a configured build or a general enquiry from /contact. Both land in the
    same table so sales reads one list and one series of reference numbers."""

    build = "build"
    enquiry = "enquiry"


class QuoteUseCaseEnum(StrEnum):
    """This module's own use cases, beyond the standard CRUD set ``UseCaseEnum`` names.

    ``submit_quote`` is not here: submitting a build *is* the create shape, so it replaces
    ``UseCaseEnum.create`` in ``QuoteService.init_use_cases`` rather than sitting beside it. An
    enquiry is a second create over the same table, which the standard set has no name for.
    """

    submit_enquiry = "submit_enquiry"
