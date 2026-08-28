"""The template method, and the one property that makes it worth having.

No database and no web framework here: a use case that needs either is a use case that has
reached through a layer it should not have.
"""

import pytest

from app.core.application.dtos import BaseOutput
from app.core.application.mappers import BaseMapper
from app.core.application.services import BaseService
from app.core.application.use_cases import BaseUseCase, GetByIdUseCase, ListUseCase
from app.core.domain.enums import UseCaseEnum
from app.core.domain.exceptions import BaseError, NotFoundError
from app.core.domain.filters import BaseFilter
from app.core.domain.interfaces import IBaseRepository
from app.core.domain.models import BaseEntity


class Widget(BaseEntity):
    name: str


class WidgetOutput(BaseOutput):
    name: str


class WidgetMapper(BaseMapper):
    def to_api(self, entity: Widget) -> WidgetOutput:
        return WidgetOutput(name=entity.name)

    def to_domain(self, create_request) -> Widget:  # pragma: no cover - unused here
        return Widget(name=create_request.name)

    def to_update(self, entity, update_request) -> Widget:  # pragma: no cover - unused here
        return entity


class FakeRepository(IBaseRepository):
    """A dictionary with a repository's manners. That this is enough is the point."""

    def __init__(self, rows: list[Widget] | None = None) -> None:
        self.rows = rows or []
        self.calls: list[str] = []

    def create(self, entity: Widget) -> Widget:
        self.calls.append("create")
        self.rows.append(entity)
        return entity

    def list(self, filters: BaseFilter) -> list[Widget]:
        self.calls.append("list")
        if filters.id_eq is not None:
            return [row for row in self.rows if row.id == filters.id_eq]
        return list(self.rows)

    def count(self, filters: BaseFilter) -> int:
        self.calls.append("count")
        return len(self.list(filters))

    def update(self, entity: Widget) -> Widget:  # pragma: no cover - unused here
        self.calls.append("update")
        return entity

    def delete(self, entity: Widget) -> None:  # pragma: no cover - unused here
        self.calls.append("delete")


def _use_case(cls, repository: FakeRepository):
    return cls(mapper=WidgetMapper(), filter_class=BaseFilter, repository=repository)


def test_exec_calls_the_four_hooks_in_order() -> None:
    """``pre_run -> validate -> run -> post_run``, stated once here so that a feature overriding
    a hook knows what it is between."""
    order: list[str] = []

    class Recording(BaseUseCase):
        def pre_run(self) -> None:
            order.append("pre_run")

        def validate(self) -> None:
            order.append("validate")

        def run(self) -> None:
            order.append("run")

        def post_run(self) -> None:
            order.append("post_run")

    Recording().exec()

    assert order == ["pre_run", "validate", "run", "post_run"]


def test_validate_aborts_before_run_touches_the_repository() -> None:
    """The property the whole template exists for: a refusal raised from ``validate`` happens
    before anything is written, by construction rather than by every author remembering the
    order."""
    repository = FakeRepository([Widget(id=1, name="winch")])

    class RefusingList(ListUseCase):
        def validate(self, filters: BaseFilter) -> None:
            raise BaseError("not today", status_code=403, code="forbidden")

    with pytest.raises(BaseError) as exc:
        _use_case(RefusingList, repository).exec(BaseFilter())

    assert exc.value.status_code == 403
    assert exc.value.code == "forbidden"
    assert repository.calls == []


def test_list_maps_every_entity_through_the_mapper() -> None:
    repository = FakeRepository([Widget(id=1, name="winch"), Widget(id=2, name="awning")])

    outputs = _use_case(ListUseCase, repository).exec(BaseFilter())

    assert [output.name for output in outputs] == ["winch", "awning"]
    assert repository.calls == ["list"]


def test_get_by_id_raises_rather_than_answering_with_none() -> None:
    """A ``None`` here becomes a 200 with a ``null`` body at whichever call site forgets to
    check. Raising makes the 404 the default rather than the diligent path."""
    repository = FakeRepository([])

    with pytest.raises(NotFoundError) as exc:
        _use_case(GetByIdUseCase, repository).exec(7)

    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


def test_a_service_registers_the_full_crud_set() -> None:
    class WidgetService(BaseService):
        mapper = WidgetMapper()
        filter_class = BaseFilter

    service = WidgetService(repository=FakeRepository())

    assert set(service.use_cases) == set(UseCaseEnum)


def test_a_service_without_a_mapper_refuses_to_be_built() -> None:
    """Caught at construction, where the message can name the class, rather than as an
    ``AttributeError`` inside whichever use case is called first."""

    class Incomplete(BaseService):
        pass

    with pytest.raises(ValueError, match="mapper"):
        Incomplete(repository=FakeRepository())


def test_a_service_can_swap_one_use_case_and_keep_the_rest() -> None:
    """``init_use_cases`` is the override point: a feature changes the create path without
    reimplementing the other six."""

    class OnlyBristlecones(ListUseCase):
        pass

    class WidgetService(BaseService):
        mapper = WidgetMapper()
        filter_class = BaseFilter

        def init_use_cases(self, deps: dict) -> dict:
            return {**super().init_use_cases(deps), UseCaseEnum.list: OnlyBristlecones(**deps)}

    service = WidgetService(repository=FakeRepository())

    assert isinstance(service.use_cases[UseCaseEnum.list], OnlyBristlecones)
    assert isinstance(service.use_cases[UseCaseEnum.get_by_id], GetByIdUseCase)
