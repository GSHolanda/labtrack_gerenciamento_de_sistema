import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.models import Client
from app.repositories.base import BaseRepository, PageRequest


class ClientRepository(BaseRepository[Client]):
    model = Client
    sortable = {"code": Client.code, "name": Client.name}  # noqa: RUF012


@pytest.fixture
def repository(session: Session) -> ClientRepository:
    for number, name in enumerate(["Delta", "Alfa", "Charlie", "Bravo", "Echo"], start=1):
        session.add(Client(code=f"CLI-{number:03d}", name=name))
    session.commit()
    return ClientRepository(session)


def test_paginate_returns_requested_page_and_total(repository: ClientRepository) -> None:
    result = repository.paginate(select(Client), PageRequest(page=2, size=2, sort="name"))

    assert result.total == 5
    assert [client.name for client in result.items] == ["Charlie", "Delta"]


def test_paginate_supports_descending_sort(repository: ClientRepository) -> None:
    result = repository.paginate(select(Client), PageRequest(size=2, sort="-code"))

    assert [client.code for client in result.items] == ["CLI-005", "CLI-004"]


def test_paginate_counts_filtered_rows(repository: ClientRepository) -> None:
    statement = select(Client).where(Client.name.in_(["Alfa", "Bravo"]))

    assert repository.paginate(statement, PageRequest()).total == 2


def test_sorting_by_unlisted_field_is_rejected(repository: ClientRepository) -> None:
    with pytest.raises(BusinessRuleError) as error:
        repository.paginate(select(Client), PageRequest(sort="tax_id"))

    assert error.value.code == "INVALID_SORT_FIELD"
