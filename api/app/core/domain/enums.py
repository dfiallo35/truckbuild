"""Enumerations shared by every module's domain."""

from enum import StrEnum


class UseCaseEnum(StrEnum):
    """The standard CRUD shapes ``BaseService`` builds for every feature.

    A service keys ``self.use_cases`` off these rather than off strings so that swapping in a
    feature's own subclass (``init_use_cases``) is a dictionary write CI can see the key of,
    rather than a typo that silently registers an eighth use case nobody calls.
    """

    create = "create"
    list = "list"
    paginate = "paginate"
    get_by_id = "get_by_id"
    update = "update"
    batch_update = "batch_update"
    delete = "delete"
