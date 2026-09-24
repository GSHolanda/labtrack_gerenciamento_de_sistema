"""Casos de uso de amostras: registro, testes atribuídos e workflow de status."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.audit import AuditAction
from app.domain.enums import RoleCode, SampleStatus, SampleTestStatus
from app.domain.pagination import PageRequest, PageResult
from app.domain.sample_code import format_sample_code
from app.domain.specification import SpecLimits, resolve_limits
from app.domain.workflow import (
    ACTIONS_REQUIRING_REASON,
    SampleAction,
    ensure_editable,
    is_final,
    next_status,
)
from app.models import Sample, SampleStatusHistory, SampleTest, TestDefinition, User
from app.repositories.master_data_repository import (
    ClientRepository,
    ProductRepository,
    TestDefinitionRepository,
)
from app.repositories.sample_repository import SampleRepository, SampleTestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.samples import SampleCreate, SampleFilter, SampleUpdate
from app.services.audit_service import AuditService, actor_of, diff, snapshot

# Tolerância para diferença de relógio entre o cliente e o servidor (RN-03).
CLOCK_SKEW = timedelta(minutes=5)
SAMPLE_FIELDS = ("lot_number", "origin", "priority", "responsible_id", "notes")

Precondition = Callable[[Sample], None]


class SampleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.samples = SampleRepository(session)
        self.sample_tests = SampleTestRepository(session)
        self.products = ProductRepository(session)
        self.clients = ClientRepository(session)
        self.tests = TestDefinitionRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditService(session)

    # --- Consultas ------------------------------------------------------------

    def search(self, filters: SampleFilter, page: PageRequest) -> PageResult[Sample]:
        return self.samples.search(filters, page)

    def get(self, sample_id: int) -> Sample:
        sample = self.samples.get_detailed(sample_id)
        if sample is None:
            raise NotFoundError(f"Amostra {sample_id} não encontrada.", code="SAMPLE_NOT_FOUND")
        return sample

    def status_history(self, sample_id: int) -> list[SampleStatusHistory]:
        self.get(sample_id)
        return self.samples.status_history(sample_id)

    # --- Registro -------------------------------------------------------------

    def create(self, data: SampleCreate, actor: User) -> Sample:
        product = self.products.get(data.product_id)
        if product is None or not product.is_active:
            raise BusinessRuleError(
                "Produto inexistente ou inativo.", code="INVALID_PRODUCT"
            )  # RN-02
        client = self.clients.get(data.client_id)
        if client is None or not client.is_active:
            raise BusinessRuleError("Cliente inexistente ou inativo.", code="INVALID_CLIENT")
        received_at = _as_utc(data.received_at)
        if received_at > datetime.now(UTC) + CLOCK_SKEW:  # RN-03
            raise BusinessRuleError(
                "A data de recebimento não pode estar no futuro.", code="RECEIVED_AT_IN_FUTURE"
            )
        if data.responsible_id is not None:
            self._ensure_analyst(data.responsible_id)

        year = received_at.year
        sample = self.samples.add(
            Sample(
                sample_code=format_sample_code(year, self.samples.next_sequence(year)),  # RN-01
                product_id=product.id,
                client_id=client.id,
                lot_number=data.lot_number,
                origin=data.origin,
                received_at=received_at,
                priority=data.priority,
                status=SampleStatus.RECEIVED,
                responsible_id=data.responsible_id,
                notes=data.notes,
                created_by_id=actor.id,
            )
        )
        self._add_history(sample, None, SampleStatus.RECEIVED, actor, None)
        self.audit.record(
            actor_of(actor),
            AuditAction.SAMPLE_CREATED,
            entity_type="sample",
            entity_id=sample.id,
            entity_label=sample.sample_code,
            sample_id=sample.id,
            new_value={
                "product": product.code,
                "client": client.code,
                "lot_number": sample.lot_number,
                "origin": sample.origin,
                "received_at": sample.received_at,
                "priority": sample.priority,
                "status": sample.status,
            },
        )

        # RN-04: plano analítico do produto atribuído automaticamente.
        plan = [
            (spec.test_definition, SpecLimits(spec.spec_min, spec.spec_max))
            for spec in self.products.specifications(product.id)
            if spec.test_definition.is_active
        ]
        if plan:
            self._assign(sample, plan, actor, automatic=True)

        self.session.commit()
        return self.get(sample.id)

    def update(self, sample_id: int, data: SampleUpdate, actor: User) -> Sample:
        sample = self.get(sample_id)
        ensure_editable(sample.status, sample.sample_code)
        _ensure_version(sample, data.version)
        changes = data.model_dump(exclude_unset=True, exclude={"version"})
        if changes.get("responsible_id") is not None:
            self._ensure_analyst(changes["responsible_id"])

        before = snapshot(sample, SAMPLE_FIELDS)
        for name, value in changes.items():
            setattr(sample, name, value)
        old_value, new_value = diff(before, snapshot(sample, SAMPLE_FIELDS))
        if new_value:
            self.session.flush()
            self._audit_sample(sample, actor, AuditAction.SAMPLE_UPDATED, old_value, new_value)
        self.session.commit()
        return self.get(sample.id)

    # --- Testes atribuídos ----------------------------------------------------

    def assign_tests(self, sample_id: int, test_definition_ids: list[int], actor: User) -> Sample:
        sample = self.get(sample_id)
        ensure_editable(sample.status, sample.sample_code)  # RN-05

        unique_ids = list(dict.fromkeys(test_definition_ids))
        definitions = self.tests.get_many(unique_ids)
        invalid = [i for i in unique_ids if i not in definitions or not definitions[i].is_active]
        if invalid:
            raise BusinessRuleError(
                "Tipos de teste inexistentes ou inativos.",
                code="INVALID_TEST_DEFINITION",
                details={"test_definition_ids": invalid},
            )
        already = {test.test_definition_id for test in sample.tests}
        duplicated = [definitions[i].code for i in unique_ids if i in already]
        if duplicated:
            raise ConflictError(
                "Testes já atribuídos à amostra.",
                code="TEST_ALREADY_ASSIGNED",
                details={"tests": duplicated},
            )

        overrides = {
            spec.test_definition_id: SpecLimits(spec.spec_min, spec.spec_max)
            for spec in self.products.specifications(sample.product_id)
        }
        self._assign(
            sample,
            [(definitions[i], overrides.get(i)) for i in unique_ids],
            actor,
            automatic=False,
        )
        self.session.commit()
        self.session.expire(sample, ["tests"])
        return self.get(sample.id)

    def cancel_test(self, sample_test_id: int, reason: str, actor: User) -> Sample:
        sample_test = self.sample_tests.get(sample_test_id)
        if sample_test is None:
            raise NotFoundError(
                f"Teste atribuído {sample_test_id} não encontrado.", code="SAMPLE_TEST_NOT_FOUND"
            )
        sample = sample_test.sample
        ensure_editable(sample.status, sample.sample_code)
        if sample_test.status != SampleTestStatus.PENDING:  # RN-07
            raise ConflictError(
                "Apenas testes pendentes podem ser cancelados.",
                code="SAMPLE_TEST_NOT_PENDING",
                details={"status": sample_test.status},
            )
        sample_test.status = SampleTestStatus.CANCELLED
        self.session.flush()
        self.audit.record(
            actor_of(actor),
            AuditAction.TEST_CANCELLED,
            entity_type="sample_test",
            entity_id=sample_test.id,
            entity_label=f"{sample.sample_code} / {sample_test.test_definition.code}",
            sample_id=sample.id,
            old_value={"status": SampleTestStatus.PENDING},
            new_value={"status": SampleTestStatus.CANCELLED},
            reason=reason,
        )
        self.session.commit()
        return self.get(sample.id)

    # --- Workflow -------------------------------------------------------------

    def start_analysis(self, sample_id: int, actor: User) -> Sample:
        return self._transition(sample_id, SampleAction.START_ANALYSIS, actor, None, _has_tests)

    def submit_for_review(self, sample_id: int, actor: User) -> Sample:
        return self._transition(
            sample_id, SampleAction.SUBMIT_FOR_REVIEW, actor, None, _all_tests_completed
        )

    def cancel(self, sample_id: int, reason: str, actor: User) -> Sample:
        return self._transition(sample_id, SampleAction.CANCEL, actor, reason)

    def _transition(
        self,
        sample_id: int,
        action: SampleAction,
        actor: User,
        reason: str | None,
        precondition: Precondition | None = None,
    ) -> Sample:
        """Aplica uma ação do workflow: valida, muda o status e registra histórico e auditoria."""
        sample = self.get(sample_id)
        target = next_status(sample.status, action)
        if action in ACTIONS_REQUIRING_REASON and not reason:
            raise BusinessRuleError("Informe a justificativa.", code="REASON_REQUIRED")
        if precondition:
            precondition(sample)

        previous = sample.status
        now = datetime.now(UTC)
        sample.status = target
        if action == SampleAction.SUBMIT_FOR_REVIEW:
            sample.submitted_at = now
        if is_final(target):
            sample.completed_at = now
        self.session.flush()

        self._add_history(sample, previous, target, actor, reason)
        self._audit_sample(
            sample,
            actor,
            AuditAction.SAMPLE_STATUS_CHANGED,
            {"status": previous},
            {"status": target},
            reason,
        )
        self.session.commit()
        return self.get(sample.id)

    # --- Auxiliares -----------------------------------------------------------

    def _assign(
        self,
        sample: Sample,
        items: list[tuple[TestDefinition, SpecLimits | None]],
        actor: User,
        *,
        automatic: bool,
    ) -> None:
        for definition, override in items:
            limits = resolve_limits(  # RN-06: snapshot da especificação vigente
                SpecLimits(definition.spec_min, definition.spec_max), override
            )
            self.sample_tests.add(
                SampleTest(
                    sample_id=sample.id,
                    test_definition_id=definition.id,
                    status=SampleTestStatus.PENDING,
                    spec_min=limits.spec_min,
                    spec_max=limits.spec_max,
                    unit=definition.unit,
                    assigned_by_id=actor.id,
                )
            )
        self._audit_sample(
            sample,
            actor,
            AuditAction.TESTS_ASSIGNED,
            None,
            {"tests": [definition.code for definition, _ in items], "automatic": automatic},
        )

    def _add_history(
        self,
        sample: Sample,
        from_status: str | None,
        to_status: str,
        actor: User,
        reason: str | None,
    ) -> None:
        self.session.add(
            SampleStatusHistory(
                sample_id=sample.id,
                from_status=from_status,
                to_status=to_status,
                changed_by_id=actor.id,
                changed_at=datetime.now(UTC),
                reason=reason,
            )
        )

    def _audit_sample(
        self,
        sample: Sample,
        actor: User,
        action: AuditAction,
        old_value: Any,
        new_value: Any,
        reason: str | None = None,
    ) -> None:
        self.audit.record(
            actor_of(actor),
            action,
            entity_type="sample",
            entity_id=sample.id,
            entity_label=sample.sample_code,
            sample_id=sample.id,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
        )

    def _ensure_analyst(self, user_id: int) -> None:
        user = self.users.get(user_id)
        if user is None or not user.is_active or user.role.code != RoleCode.ANALYST:
            raise BusinessRuleError(
                "O responsável deve ser um analista ativo.", code="INVALID_RESPONSIBLE"
            )


def _active_tests(sample: Sample) -> list[SampleTest]:
    return [test for test in sample.tests if test.status != SampleTestStatus.CANCELLED]


def _has_tests(sample: Sample) -> None:
    if not _active_tests(sample):  # RN-08
        raise ConflictError(
            f"A amostra {sample.sample_code} não tem testes atribuídos.", code="NO_TESTS_ASSIGNED"
        )


def _all_tests_completed(sample: Sample) -> None:
    _has_tests(sample)
    pending = [
        test.test_definition.code
        for test in _active_tests(sample)
        if test.status != SampleTestStatus.COMPLETED
    ]
    if pending:  # RN-10
        raise ConflictError(
            "Existem testes sem resultado.", code="TESTS_PENDING", details={"tests": pending}
        )


def _ensure_version(sample: Sample, version: int) -> None:
    if sample.version != version:
        raise ConflictError(
            "A amostra foi alterada por outro usuário. Recarregue e tente novamente.",
            code="CONCURRENT_MODIFICATION",
            details={"current_version": sample.version, "sent_version": version},
        )


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
