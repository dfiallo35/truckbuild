"""The one place a query for the common filters is written.

``filter()`` is the extension point: a feature's repository overrides it, applies its own
narrowing, and calls ``super().filter(...)`` for the shared half. Every field it keys off is
named by the ``_eq`` / ``_in`` / ``_ilike`` / ``_gte`` / ``_lte`` convention in
``core/domain/filters.py``.

Sync, with a request-scoped ``Session`` injected rather than a connection opened per call: the
service is sync, and quote submission needs one transaction spanning its ref-collision retry.
FastAPI supplies the session through ``Depends(get_session)`` at the composition root, which
also makes it the seam a test overrides.
"""

from sqlalchemy.sql import Select
from sqlmodel import Session, func, select

from app.core.domain.exceptions import NotFoundError, NotValidOrderByError
from app.core.domain.filters import BaseFilter
from app.core.domain.interfaces import IBaseRepository
from app.core.domain.models import BaseEntity
from app.core.infrastructure.postgres.mappers import BaseMapper
from app.core.infrastructure.postgres.tables import BaseTable


class BaseRepositoryPostgres(IBaseRepository):
    mapper: BaseMapper
    table_class: type[BaseTable]

    def __init__(self, session: Session) -> None:
        self.session = session

    def filter(self, filters: BaseFilter, query: Select) -> Select:
        """Apply the filters every table supports, then the window, then the ordering."""
        if filters.id_eq is not None:
            query = query.where(self.table_class.id == filters.id_eq)
        if filters.created_at_gte is not None:
            query = query.where(self.table_class.created_at >= filters.created_at_gte)
        if filters.created_at_lte is not None:
            query = query.where(self.table_class.created_at <= filters.created_at_lte)
        if filters.updated_at_gte is not None:
            query = query.where(self.table_class.updated_at >= filters.updated_at_gte)
        if filters.updated_at_lte is not None:
            query = query.where(self.table_class.updated_at <= filters.updated_at_lte)

        if filters.limit is not None:
            query = query.limit(filters.limit)
        if filters.offset is not None:
            query = query.offset(filters.offset)

        if filters.order_by:
            order_by = filters.order_by
            descending = order_by.startswith("-")
            order_by = order_by.lstrip("-")

            column = getattr(self.table_class, order_by, None)
            if column is None:
                # Rejected rather than ignored: a silently dropped sort is a page that looks
                # right, is in the wrong order, and gives nobody a reason to look.
                raise NotValidOrderByError(order_by, self.table_class.__tablename__)
            query = query.order_by(column.desc() if descending else column)

        return query

    def create(self, entity: BaseEntity) -> BaseEntity:
        table = self.mapper.to_table(entity)
        self.session.add(table)
        self.session.flush()
        self.session.refresh(table)
        return self.mapper.to_domain(table)

    def list(self, filters: BaseFilter) -> list[BaseEntity]:
        query = self.filter(filters, select(self.table_class))
        return [self.mapper.to_domain(row) for row in self.session.exec(query).all()]

    def count(self, filters: BaseFilter) -> int:
        # The window and the ordering are what the count must *not* carry: a count with the
        # page's LIMIT applied answers "how many are on this page", which is the number the
        # caller already has.
        counted = filters.model_copy(update={"limit": None, "offset": None, "order_by": None})
        query = self.filter(counted, select(func.count()).select_from(self.table_class))
        return self.session.exec(query).one()

    def update(self, entity: BaseEntity) -> BaseEntity:
        row = self.session.get(self.table_class, entity.id)
        if row is None:
            raise NotFoundError(f"no {self.table_class.__tablename__} with id {entity.id}")

        for key, value in self.mapper.to_table(entity).model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self.session.flush()
        self.session.refresh(row)
        return self.mapper.to_domain(row)

    def delete(self, entity: BaseEntity) -> None:
        row = self.session.get(self.table_class, entity.id)
        if row is None:
            raise NotFoundError(f"no {self.table_class.__tablename__} with id {entity.id}")
        self.session.delete(row)
        self.session.flush()
