"""One operation, one class.

``BaseUseCase`` is a template method: ``exec`` drives ``pre_run -> validate -> run -> post_run``
and features override the *hooks*, never ``exec``. That is what keeps "look it up, then check
the rule, then write, then tell the cache" in the same order in every feature, and what makes a
new step (an audit line, a revalidation) an override rather than an edit to shared machinery.

The seven subclasses below cover the standard CRUD shapes so that a feature whose endpoint is
one of them writes a filter and a mapper rather than another loop over a session.

Sync, not async, unlike the reference repository: this service is sync throughout, and quote
submission needs one transaction spanning the ref-collision retry. Going async is a change with
its own risk, not a rider on a layering refactor -- see Stage 9 of the archived development plan (Notion).
"""

from app.core.application.dtos import (
    BaseBatchUpdateRequest,
    BaseCreateRequest,
    BaseOutput,
    BasePaginatedOutput,
    BaseUpdateRequest,
)
from app.core.application.mappers import BaseMapper
from app.core.domain.exceptions import NotFoundError
from app.core.domain.filters import BaseFilter
from app.core.domain.interfaces import IBaseRepository
from app.core.domain.models import BaseEntity


class BaseUseCase:
    """The template. Everything below overrides hooks on it.

    All three collaborators are optional because not every use case has all three -- a use case
    that only invalidates a cache has no mapper, and one that only reads has nothing to map back
    from a request.
    """

    def __init__(
        self,
        mapper: BaseMapper | None = None,
        filter_class: type[BaseFilter] | None = None,
        repository: IBaseRepository | None = None,
        *args,
        **kwargs,
    ) -> None:
        self.mapper = mapper
        self.filter_class = filter_class
        self.repository = repository

    def get_output(self, entity: BaseEntity | list[BaseEntity]) -> BaseOutput | list[BaseOutput]:
        if isinstance(entity, list):
            return [self.mapper.to_api(e) for e in entity]
        return self.mapper.to_api(entity)

    def pre_run(self):
        """Everything that must happen before the operation is judged: load, default, normalize."""

    def validate(self):
        """Refuse here. Raising a ``BaseError`` from this hook aborts before ``run`` touches the
        repository, which is the property that makes "validate then write" true by construction
        rather than by every author remembering the order."""

    def run(self):
        """The operation itself."""  # pragma: no cover - every concrete use case overrides this

    def post_run(self):
        """Everything the operation implies: cache invalidation, mail, an audit line."""

    def exec(self):
        self.pre_run()
        self.validate()
        self.run()
        self.post_run()


class CreateUseCase(BaseUseCase):
    def pre_run(self, create_request: BaseCreateRequest, entity: BaseEntity) -> BaseEntity:
        return entity

    def validate(self, create_request: BaseCreateRequest, entity: BaseEntity) -> None:
        pass

    def run(self, create_request: BaseCreateRequest, entity: BaseEntity) -> BaseEntity:
        return self.repository.create(entity)

    def post_run(self, entity: BaseEntity, created_entity: BaseEntity) -> BaseEntity:
        return created_entity

    def exec(self, create_request: BaseCreateRequest) -> BaseOutput:
        entity = self.mapper.to_domain(create_request)
        entity = self.pre_run(create_request=create_request, entity=entity)
        self.validate(create_request=create_request, entity=entity)
        created_entity = self.run(create_request=create_request, entity=entity)
        created_entity = self.post_run(entity=entity, created_entity=created_entity)
        return self.get_output(entity=created_entity)


# UpdateUseCase, BatchUpdateUseCase and DeleteUseCase have no caller in this service and will
# still have none when the migration finishes: the catalog is seeded from a versioned YAML file
# rather than edited over HTTP, and a submitted lead is a record of what was offered on a date,
# never mutated. They are marked no-cover rather than deleted because ``BaseService`` registers
# the full CRUD set and a feature that does write over HTTP should find them here -- but
# scaffolding that lies about being exercised is worse than scaffolding that admits it. The
# reference repository marks its own unreached ``BatchUpdateUseCase`` the same way.
class UpdateUseCase(BaseUseCase):  # pragma: no cover - no write endpoint in this service
    def pre_run(self, update_request: BaseUpdateRequest, entity: BaseEntity) -> BaseEntity:
        return entity

    def validate(
        self,
        update_request: BaseUpdateRequest,
        entity: BaseEntity,
        updated_entity: BaseEntity,
    ) -> None:
        pass

    def run(
        self,
        update_request: BaseUpdateRequest,
        entity: BaseEntity,
        updated_entity: BaseEntity,
    ) -> BaseEntity:
        return self.repository.update(updated_entity)

    def post_run(
        self,
        update_request: BaseUpdateRequest,
        entity: BaseEntity,
        updated_entity: BaseEntity,
    ) -> BaseEntity:
        return updated_entity

    def exec(self, id: int, update_request: BaseUpdateRequest) -> BaseOutput:
        entity = self._load(id)
        entity = self.pre_run(update_request=update_request, entity=entity)
        updated_entity = self.mapper.to_update(entity, update_request)
        self.validate(update_request=update_request, entity=entity, updated_entity=updated_entity)
        updated_entity = self.run(
            update_request=update_request, entity=entity, updated_entity=updated_entity
        )
        updated_entity = self.post_run(
            update_request=update_request, entity=entity, updated_entity=updated_entity
        )
        return self.get_output(entity=updated_entity)

    def _load(self, id: int) -> BaseEntity:
        entities = self.repository.list(self.filter_class(id_eq=id))
        if not entities:
            raise NotFoundError(f"nothing found with id {id}")
        return entities[0]


class BatchUpdateUseCase(UpdateUseCase):  # pragma: no cover - same, and no batch route either
    def exec(self, batch_update_request: BaseBatchUpdateRequest) -> list[BaseOutput]:
        outputs = []
        for update_request in batch_update_request.items:
            outputs.append(super().exec(update_request.id, update_request))
        return outputs


class DeleteUseCase(BaseUseCase):  # pragma: no cover - nothing in this service deletes
    def pre_run(self, entity: BaseEntity) -> BaseEntity:
        return entity

    def validate(self, entity: BaseEntity) -> None:
        pass

    def run(self, entity: BaseEntity) -> None:
        return self.repository.delete(entity)

    def post_run(self, entity: BaseEntity, result: None) -> None:
        return result

    def exec(self, id: int) -> None:
        entities = self.repository.list(self.filter_class(id_eq=id))
        if not entities:
            raise NotFoundError(f"nothing found with id {id}")
        entity = entities[0]

        entity = self.pre_run(entity=entity)
        self.validate(entity=entity)
        result = self.run(entity=entity)
        return self.post_run(entity=entity, result=result)


class ListUseCase(BaseUseCase):
    def pre_run(self, filters: BaseFilter) -> BaseFilter:
        return filters

    def validate(self, filters: BaseFilter) -> None:
        pass

    def run(self, filters: BaseFilter) -> list[BaseEntity]:
        return self.repository.list(filters)

    def post_run(self, filters: BaseFilter, entities: list[BaseEntity]) -> list[BaseEntity]:
        return entities

    def exec(self, filters: BaseFilter) -> list[BaseOutput]:
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        entities = self.run(filters=filters)
        entities = self.post_run(filters=filters, entities=entities)
        return self.get_output(entities)


class PaginateUseCase(BaseUseCase):
    """A list plus the total it was taken from -- two queries, because a page with no total is
    a page with no "of 412" and no last page."""

    def pre_run(self, filters: BaseFilter) -> BaseFilter:
        return filters

    def validate(self, filters: BaseFilter) -> None:
        pass

    def run(self, filters: BaseFilter) -> tuple[int, list[BaseEntity]]:
        return self.repository.count(filters), self.repository.list(filters)

    def post_run(self, filters: BaseFilter, entities: list[BaseEntity]) -> list[BaseEntity]:
        return entities

    def exec(self, filters: BaseFilter) -> BasePaginatedOutput[BaseOutput]:
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        total, entities = self.run(filters=filters)
        entities = self.post_run(filters=filters, entities=entities)
        return BasePaginatedOutput(
            items=self.get_output(entities),
            total=total,
            limit=filters.limit,
            offset=filters.offset,
        )


class GetByIdUseCase(BaseUseCase):
    """One entity or a 404 -- never ``None``.

    Returning ``None`` for "not found" pushes the decision to every caller, and one of them
    eventually forgets and serializes it as ``null`` with a 200.
    """

    def pre_run(self, filters: BaseFilter) -> BaseFilter:
        return filters

    def validate(self, filters: BaseFilter) -> None:
        pass

    def run(self, filters: BaseFilter) -> BaseEntity:
        entities = self.repository.list(filters)
        if not entities:
            raise NotFoundError(f"nothing found with id {filters.id_eq}")
        return entities[0]

    def post_run(self, filters: BaseFilter, entity: BaseEntity) -> BaseEntity:
        return entity

    def exec(self, id: int) -> BaseOutput:
        filters = self.filter_class(id_eq=id)
        filters = self.pre_run(filters=filters)
        self.validate(filters=filters)
        entity = self.run(filters=filters)
        entity = self.post_run(filters=filters, entity=entity)
        return self.get_output(entity)
