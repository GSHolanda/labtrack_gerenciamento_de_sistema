from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from app.domain.pagination import PageRequest, PageResult
from app.models import Client, Product, ProductSpecification, TestDefinition
from app.repositories.base import BaseRepository, ModelT
from app.schemas.master_data import MasterDataFilter


class _CodedRepository(BaseRepository[ModelT]):
    """Base dos cadastros com ``code`` único, ``name`` e ``is_active``."""

    search_columns: Sequence[InstrumentedAttribute[Any]] = ()

    def find_by_code(self, code: str) -> ModelT | None:
        return self.session.scalar(
            select(self.model).where(func.upper(self.model.code) == code.upper())  # type: ignore[attr-defined]
        )

    def search(self, filters: MasterDataFilter, page: PageRequest) -> PageResult[ModelT]:
        statement = select(self.model)
        if filters.is_active is not None:
            statement = statement.where(self.model.is_active == filters.is_active)  # type: ignore[attr-defined]
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            statement = statement.where(
                or_(*(func.lower(column).like(pattern) for column in self.search_columns))
            )
        return self.paginate(statement, page)


class ClientRepository(_CodedRepository[Client]):
    model = Client
    search_columns = (Client.code, Client.name, Client.tax_id)
    sortable = {"code": Client.code, "name": Client.name}  # noqa: RUF012
    default_sort = (Client.name,)

    def exists_with_tax_id(self, tax_id: str, *, exclude_id: int | None = None) -> bool:
        statement = select(Client.id).where(Client.tax_id == tax_id)
        if exclude_id is not None:
            statement = statement.where(Client.id != exclude_id)
        return self.session.scalar(statement) is not None


class ProductRepository(_CodedRepository[Product]):
    model = Product
    search_columns = (Product.code, Product.name, Product.category)
    sortable = {"code": Product.code, "name": Product.name, "category": Product.category}  # noqa: RUF012
    default_sort = (Product.name,)

    def specifications(self, product_id: int) -> list[ProductSpecification]:
        return list(
            self.session.scalars(
                select(ProductSpecification)
                .join(ProductSpecification.test_definition)
                .where(ProductSpecification.product_id == product_id)
                .order_by(TestDefinition.name)
            )
        )


class TestDefinitionRepository(_CodedRepository[TestDefinition]):
    __test__ = False

    model = TestDefinition
    search_columns = (TestDefinition.code, TestDefinition.name, TestDefinition.method)
    sortable = {"code": TestDefinition.code, "name": TestDefinition.name}  # noqa: RUF012
    default_sort = (TestDefinition.name,)

    def get_many(self, ids: Sequence[int]) -> dict[int, TestDefinition]:
        rows = self.session.scalars(select(TestDefinition).where(TestDefinition.id.in_(ids)))
        return {row.id: row for row in rows}
