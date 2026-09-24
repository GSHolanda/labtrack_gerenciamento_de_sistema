"""Casos de uso dos cadastros (clientes, produtos, tipos de teste, plano analítico)."""

from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.audit import AuditAction
from app.domain.pagination import PageRequest, PageResult
from app.domain.specification import SpecLimits, resolve_limits, validate_limits
from app.models import Client, Product, ProductSpecification, TestDefinition, User
from app.repositories.master_data_repository import (
    ClientRepository,
    ProductRepository,
    TestDefinitionRepository,
)
from app.schemas.master_data import (
    ClientCreate,
    ClientUpdate,
    MasterDataFilter,
    ProductCreate,
    ProductUpdate,
    SpecificationItem,
    SpecificationRead,
    TestDefinitionCreate,
    TestDefinitionUpdate,
)
from app.services.audit_service import AuditService, actor_of, diff, snapshot

CLIENT_FIELDS = ("code", "name", "tax_id", "contact_email", "is_active")
PRODUCT_FIELDS = ("code", "name", "category", "description", "is_active")
TEST_FIELDS = (
    "code",
    "name",
    "unit",
    "spec_min",
    "spec_max",
    "method",
    "instrument_type",
    "decimal_places",
    "description",
    "is_active",
)


class MasterDataService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.clients = ClientRepository(session)
        self.products = ProductRepository(session)
        self.tests = TestDefinitionRepository(session)
        self.audit = AuditService(session)

    # --- Clientes -------------------------------------------------------------

    def search_clients(self, filters: MasterDataFilter, page: PageRequest) -> PageResult[Client]:
        return self.clients.search(filters, page)

    def get_client(self, client_id: int) -> Client:
        return _require(self.clients.get(client_id), "Cliente", client_id, "CLIENT_NOT_FOUND")

    def create_client(self, data: ClientCreate, actor: User) -> Client:
        if self.clients.find_by_code(data.code):
            raise _duplicate("cliente", "código", data.code)
        if data.tax_id and self.clients.exists_with_tax_id(data.tax_id):
            raise _duplicate("cliente", "CNPJ", data.tax_id)
        client = self.clients.add(Client(**data.model_dump()))
        return self._created(client, AuditAction.CLIENT_CREATED, "client", CLIENT_FIELDS, actor)

    def update_client(self, client_id: int, data: ClientUpdate, actor: User) -> Client:
        client = self.get_client(client_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("tax_id") and self.clients.exists_with_tax_id(
            changes["tax_id"], exclude_id=client.id
        ):
            raise _duplicate("cliente", "CNPJ", changes["tax_id"])
        return self._updated(
            client, changes, AuditAction.CLIENT_UPDATED, "client", CLIENT_FIELDS, actor
        )

    # --- Produtos -------------------------------------------------------------

    def search_products(self, filters: MasterDataFilter, page: PageRequest) -> PageResult[Product]:
        return self.products.search(filters, page)

    def get_product(self, product_id: int) -> Product:
        return _require(self.products.get(product_id), "Produto", product_id, "PRODUCT_NOT_FOUND")

    def create_product(self, data: ProductCreate, actor: User) -> Product:
        if self.products.find_by_code(data.code):
            raise _duplicate("produto", "código", data.code)
        product = self.products.add(Product(**data.model_dump()))
        return self._created(product, AuditAction.PRODUCT_CREATED, "product", PRODUCT_FIELDS, actor)

    def update_product(self, product_id: int, data: ProductUpdate, actor: User) -> Product:
        product = self.get_product(product_id)
        return self._updated(
            product,
            data.model_dump(exclude_unset=True),
            AuditAction.PRODUCT_UPDATED,
            "product",
            PRODUCT_FIELDS,
            actor,
        )

    def get_specifications(self, product_id: int) -> list[SpecificationRead]:
        self.get_product(product_id)
        return [_specification_read(spec) for spec in self.products.specifications(product_id)]

    def replace_specifications(
        self, product_id: int, items: list[SpecificationItem], actor: User
    ) -> list[SpecificationRead]:
        """Substitui o plano analítico do produto (testes atribuídos no registro da amostra)."""
        product = self.get_product(product_id)
        ids = [item.test_definition_id for item in items]
        if len(ids) != len(set(ids)):
            raise BusinessRuleError(
                "O mesmo teste aparece mais de uma vez no plano.", code="DUPLICATED_TEST"
            )
        definitions = self.tests.get_many(ids)
        invalid = [i for i in ids if i not in definitions or not definitions[i].is_active]
        if invalid:
            raise BusinessRuleError(
                "Tipos de teste inexistentes ou inativos.",
                code="INVALID_TEST_DEFINITION",
                details={"test_definition_ids": invalid},
            )
        for item in items:
            effective = _effective_limits(definitions[item.test_definition_id], item)
            error = validate_limits(effective.spec_min, effective.spec_max)
            if error:
                raise BusinessRuleError(
                    f"{definitions[item.test_definition_id].code}: {error}",
                    code="INVALID_SPECIFICATION",
                )

        before = [_spec_audit(spec) for spec in self.products.specifications(product_id)]
        product.specifications.clear()
        self.session.flush()
        for item in items:
            product.specifications.append(
                ProductSpecification(
                    test_definition=definitions[item.test_definition_id],
                    spec_min=item.spec_min,
                    spec_max=item.spec_max,
                )
            )
        self.session.flush()
        after = [_spec_audit(spec) for spec in self.products.specifications(product_id)]

        self.audit.record(
            actor_of(actor),
            AuditAction.SPECIFICATION_UPDATED,
            entity_type="product",
            entity_id=product.id,
            entity_label=product.code,
            old_value=before,
            new_value=after,
        )
        self.session.commit()
        return self.get_specifications(product_id)

    # --- Tipos de teste -------------------------------------------------------

    def search_test_definitions(
        self, filters: MasterDataFilter, page: PageRequest
    ) -> PageResult[TestDefinition]:
        return self.tests.search(filters, page)

    def get_test_definition(self, test_id: int) -> TestDefinition:
        return _require(self.tests.get(test_id), "Tipo de teste", test_id, "TEST_NOT_FOUND")

    def create_test_definition(self, data: TestDefinitionCreate, actor: User) -> TestDefinition:
        if self.tests.find_by_code(data.code):
            raise _duplicate("tipo de teste", "código", data.code)
        definition = self.tests.add(TestDefinition(**data.model_dump()))
        return self._created(
            definition, AuditAction.TEST_DEFINITION_CREATED, "test_definition", TEST_FIELDS, actor
        )

    def update_test_definition(
        self, test_id: int, data: TestDefinitionUpdate, actor: User
    ) -> TestDefinition:
        """Alterar limites não afeta amostras já atribuídas (elas guardam um snapshot)."""
        definition = self.get_test_definition(test_id)
        changes = data.model_dump(exclude_unset=True)
        spec_min = changes.get("spec_min", definition.spec_min)
        spec_max = changes.get("spec_max", definition.spec_max)
        if spec_min is None and spec_max is None:
            raise BusinessRuleError(
                "Informe ao menos um limite de especificação.", code="INVALID_SPECIFICATION"
            )
        error = validate_limits(spec_min, spec_max)
        if error:
            raise BusinessRuleError(error, code="INVALID_SPECIFICATION")
        return self._updated(
            definition,
            changes,
            AuditAction.TEST_DEFINITION_UPDATED,
            "test_definition",
            TEST_FIELDS,
            actor,
        )

    # --- Auxiliares -----------------------------------------------------------

    def _created(
        self,
        entity: Any,
        action: AuditAction,
        entity_type: str,
        fields: tuple[str, ...],
        actor: User,
    ) -> Any:
        self.audit.record(
            actor_of(actor),
            action,
            entity_type=entity_type,
            entity_id=entity.id,
            entity_label=entity.code,
            new_value=snapshot(entity, fields),
        )
        self.session.commit()
        return entity

    def _updated(
        self,
        entity: Any,
        changes: dict[str, Any],
        action: AuditAction,
        entity_type: str,
        fields: tuple[str, ...],
        actor: User,
    ) -> Any:
        before = snapshot(entity, fields)
        for name, value in changes.items():
            setattr(entity, name, value)
        old_value, new_value = diff(before, snapshot(entity, fields))
        if new_value:
            self.session.flush()
            self.audit.record(
                actor_of(actor),
                action,
                entity_type=entity_type,
                entity_id=entity.id,
                entity_label=entity.code,
                old_value=old_value,
                new_value=new_value,
            )
        self.session.commit()
        return entity


def _require(entity: Any, label: str, entity_id: int, code: str) -> Any:
    if entity is None:
        raise NotFoundError(f"{label} {entity_id} não encontrado.", code=code)
    return entity


def _duplicate(entity: str, field: str, value: str) -> ConflictError:
    return ConflictError(
        f"Já existe um {entity} com {field} '{value}'.",
        code="DUPLICATED_" + entity.upper().replace(" ", "_"),
    )


def _effective_limits(definition: TestDefinition, override: Any) -> SpecLimits:
    return resolve_limits(
        SpecLimits(definition.spec_min, definition.spec_max),
        SpecLimits(override.spec_min, override.spec_max),
    )


def _specification_read(spec: ProductSpecification) -> SpecificationRead:
    definition = spec.test_definition
    effective = _effective_limits(definition, spec)
    return SpecificationRead(
        test_definition_id=definition.id,
        test_code=definition.code,
        test_name=definition.name,
        unit=definition.unit,
        spec_min=effective.spec_min,
        spec_max=effective.spec_max,
        overrides_default=spec.spec_min is not None or spec.spec_max is not None,
        product_spec_min=spec.spec_min,
        product_spec_max=spec.spec_max,
    )


def _spec_audit(spec: ProductSpecification) -> dict[str, Any]:
    return {
        "test": spec.test_definition.code,
        "spec_min": spec.spec_min,
        "spec_max": spec.spec_max,
    }
