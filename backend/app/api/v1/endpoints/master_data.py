"""Cadastros: clientes, produtos (com plano analítico) e tipos de teste."""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, DbSession
from app.api.v1.endpoints._common import Paging, errors, requires
from app.domain.permissions import Permission
from app.schemas.common import Page
from app.schemas.master_data import (
    ClientCreate,
    ClientRead,
    ClientUpdate,
    MasterDataFilter,
    ProductCreate,
    ProductRead,
    ProductUpdate,
    SpecificationItem,
    SpecificationRead,
    TestDefinitionCreate,
    TestDefinitionRead,
    TestDefinitionUpdate,
)
from app.services.master_data_service import MasterDataService

router = APIRouter()

MasterDataManager = requires(Permission.MASTER_DATA_MANAGE)
TestManager = requires(Permission.TEST_DEFINITION_MANAGE)
Search = Annotated[str | None, Query(max_length=100, description="Busca em código e nome")]


def _filters(q: str | None, is_active: bool | None) -> MasterDataFilter:
    return MasterDataFilter(q=q, is_active=is_active)


def _page(result, schema):  # type: ignore[no-untyped-def]
    return Page.build(
        [schema.model_validate(item) for item in result.items],
        result.total,
        result.page,
        result.size,
    )


# --- Clientes -----------------------------------------------------------------


@router.get("/clients", response_model=Page[ClientRead], tags=["Clients"], summary="Lista clientes")
def list_clients(
    session: DbSession,
    _: CurrentUserDep,
    paging: Paging,
    q: Search = None,
    is_active: bool | None = None,
) -> Page[ClientRead]:
    result = MasterDataService(session).search_clients(_filters(q, is_active), paging)
    return _page(result, ClientRead)


@router.post(
    "/clients",
    response_model=ClientRead,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 409),
    tags=["Clients"],
    summary="Cria cliente",
)
def create_client(data: ClientCreate, session: DbSession, actor: MasterDataManager) -> ClientRead:
    return ClientRead.model_validate(MasterDataService(session).create_client(data, actor))


@router.get(
    "/clients/{client_id}", response_model=ClientRead, responses=errors(401, 404), tags=["Clients"]
)
def get_client(client_id: int, session: DbSession, _: CurrentUserDep) -> ClientRead:
    return ClientRead.model_validate(MasterDataService(session).get_client(client_id))


@router.patch(
    "/clients/{client_id}",
    response_model=ClientRead,
    responses=errors(401, 403, 404, 409),
    tags=["Clients"],
    summary="Altera ou desativa cliente",
)
def update_client(
    client_id: int, data: ClientUpdate, session: DbSession, actor: MasterDataManager
) -> ClientRead:
    return ClientRead.model_validate(
        MasterDataService(session).update_client(client_id, data, actor)
    )


# --- Produtos -----------------------------------------------------------------


@router.get(
    "/products", response_model=Page[ProductRead], tags=["Products"], summary="Lista produtos"
)
def list_products(
    session: DbSession,
    _: CurrentUserDep,
    paging: Paging,
    q: Search = None,
    is_active: bool | None = None,
) -> Page[ProductRead]:
    result = MasterDataService(session).search_products(_filters(q, is_active), paging)
    return _page(result, ProductRead)


@router.post(
    "/products",
    response_model=ProductRead,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 409),
    tags=["Products"],
    summary="Cria produto",
)
def create_product(
    data: ProductCreate, session: DbSession, actor: MasterDataManager
) -> ProductRead:
    return ProductRead.model_validate(MasterDataService(session).create_product(data, actor))


@router.get(
    "/products/{product_id}",
    response_model=ProductRead,
    responses=errors(401, 404),
    tags=["Products"],
)
def get_product(product_id: int, session: DbSession, _: CurrentUserDep) -> ProductRead:
    return ProductRead.model_validate(MasterDataService(session).get_product(product_id))


@router.patch(
    "/products/{product_id}",
    response_model=ProductRead,
    responses=errors(401, 403, 404),
    tags=["Products"],
    summary="Altera ou desativa produto",
)
def update_product(
    product_id: int, data: ProductUpdate, session: DbSession, actor: MasterDataManager
) -> ProductRead:
    return ProductRead.model_validate(
        MasterDataService(session).update_product(product_id, data, actor)
    )


@router.get(
    "/products/{product_id}/specifications",
    response_model=list[SpecificationRead],
    responses=errors(401, 404),
    tags=["Products"],
    summary="Plano analítico do produto (testes e limites efetivos)",
)
def get_specifications(
    product_id: int, session: DbSession, _: CurrentUserDep
) -> list[SpecificationRead]:
    return MasterDataService(session).get_specifications(product_id)


@router.put(
    "/products/{product_id}/specifications",
    response_model=list[SpecificationRead],
    responses=errors(401, 403, 404, 422),
    tags=["Products"],
    summary="Define o plano analítico do produto",
    description="Substitui a lista inteira. Amostras já registradas não são afetadas.",
)
def replace_specifications(
    product_id: int,
    items: list[SpecificationItem],
    session: DbSession,
    actor: MasterDataManager,
) -> list[SpecificationRead]:
    return MasterDataService(session).replace_specifications(product_id, items, actor)


# --- Tipos de teste -----------------------------------------------------------


@router.get(
    "/test-definitions",
    response_model=Page[TestDefinitionRead],
    tags=["Tests"],
    summary="Lista tipos de teste",
)
def list_test_definitions(
    session: DbSession,
    _: CurrentUserDep,
    paging: Paging,
    q: Search = None,
    is_active: bool | None = None,
) -> Page[TestDefinitionRead]:
    result = MasterDataService(session).search_test_definitions(_filters(q, is_active), paging)
    return _page(result, TestDefinitionRead)


@router.post(
    "/test-definitions",
    response_model=TestDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 409),
    tags=["Tests"],
    summary="Cria tipo de teste",
)
def create_test_definition(
    data: TestDefinitionCreate, session: DbSession, actor: TestManager
) -> TestDefinitionRead:
    return TestDefinitionRead.model_validate(
        MasterDataService(session).create_test_definition(data, actor)
    )


@router.get(
    "/test-definitions/{test_id}",
    response_model=TestDefinitionRead,
    responses=errors(401, 404),
    tags=["Tests"],
)
def get_test_definition(test_id: int, session: DbSession, _: CurrentUserDep) -> TestDefinitionRead:
    return TestDefinitionRead.model_validate(
        MasterDataService(session).get_test_definition(test_id)
    )


@router.patch(
    "/test-definitions/{test_id}",
    response_model=TestDefinitionRead,
    responses=errors(401, 403, 404, 422),
    tags=["Tests"],
    summary="Altera limites, método ou equipamento (auditado)",
    description="Amostras já atribuídas mantêm os limites vigentes no momento da atribuição.",
)
def update_test_definition(
    test_id: int, data: TestDefinitionUpdate, session: DbSession, actor: TestManager
) -> TestDefinitionRead:
    return TestDefinitionRead.model_validate(
        MasterDataService(session).update_test_definition(test_id, data, actor)
    )
