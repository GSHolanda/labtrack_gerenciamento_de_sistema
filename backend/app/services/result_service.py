"""Registro de resultados analíticos com avaliação OOS e versionamento."""

import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.domain.audit import Actor, AuditAction
from app.domain.enums import ResultSource, SampleStatus, SampleTestStatus, SpecStatus
from app.domain.pagination import PageRequest, PageResult
from app.domain.specification import evaluate
from app.models import SampleTest, TestResult, User
from app.repositories.result_repository import ResultRepository
from app.repositories.sample_repository import SampleTestRepository
from app.schemas.results import ResultEntry, ResultFilter
from app.services.audit_service import AuditService, actor_of

logger = logging.getLogger(__name__)


class ResultService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.results = ResultRepository(session)
        self.sample_tests = SampleTestRepository(session)
        self.audit = AuditService(session)

    def search(self, filters: ResultFilter, page: PageRequest) -> PageResult[TestResult]:
        return self.results.search(filters, page)

    def history(self, sample_test_id: int) -> list[TestResult]:
        self.get_sample_test(sample_test_id)
        return self.results.history(sample_test_id)

    def get_sample_test(self, sample_test_id: int) -> SampleTest:
        sample_test = self.sample_tests.get(sample_test_id)
        if sample_test is None:
            raise NotFoundError(
                f"Teste atribuído {sample_test_id} não encontrado.", code="SAMPLE_TEST_NOT_FOUND"
            )
        return sample_test

    def enter_manual(self, sample_test_id: int, data: ResultEntry, user: User) -> TestResult:
        """Lançamento manual pelo analista (primeira versão ou correção)."""
        result = self.record(
            self.get_sample_test(sample_test_id),
            data.value,
            actor=actor_of(user),
            source=ResultSource.MANUAL,
            entered_by_id=user.id,
            comment=data.comment,
            change_reason=data.change_reason,
        )
        self.session.commit()
        return result

    def record(
        self,
        sample_test: SampleTest,
        value: Decimal,
        *,
        actor: Actor,
        source: ResultSource,
        entered_by_id: int | None = None,
        instrument_id: int | None = None,
        comment: str | None = None,
        change_reason: str | None = None,
    ) -> TestResult:
        """Grava um resultado sem fazer commit (usado também pela integração de instrumentos).

        Nunca sobrescreve: uma correção marca a versão atual como não vigente e cria
        a próxima versão, exigindo justificativa (RN-17).
        """
        sample = sample_test.sample
        label = f"{sample.sample_code} / {sample_test.test_definition.code}"
        if sample.status != SampleStatus.IN_ANALYSIS:  # RN-09 e RN-11
            raise ConflictError(
                f"Resultados só podem ser registrados com a amostra em análise "
                f"(status atual: {sample.status}).",
                code="SAMPLE_NOT_IN_ANALYSIS",
                details={"status": sample.status},
            )
        if sample_test.status == SampleTestStatus.CANCELLED:
            raise ConflictError("O teste foi cancelado.", code="SAMPLE_TEST_CANCELLED")

        previous = next((r for r in sample_test.results if r.is_current), None)
        if previous is not None and not change_reason:
            raise BusinessRuleError(
                "O teste já tem resultado: informe a justificativa da correção.",
                code="CHANGE_REASON_REQUIRED",
                details={"current_value": previous.value, "version": previous.version},
            )

        spec_status = evaluate(value, sample_test.spec_min, sample_test.spec_max)  # RN-16
        if previous is not None:
            previous.is_current = False
            self.session.flush()  # libera o índice único "uma versão vigente por teste"

        result = self.results.add(
            TestResult(
                sample_test_id=sample_test.id,
                value=value,
                unit=sample_test.unit,
                spec_status=spec_status,
                source=source,
                entered_by_id=entered_by_id,
                instrument_id=instrument_id,
                version=previous.version + 1 if previous else 1,
                is_current=True,
                change_reason=change_reason if previous else None,
                comment=comment,
                entered_at=utcnow(),
            )
        )
        sample_test.status = SampleTestStatus.COMPLETED
        self.session.flush()
        self.session.expire(sample_test, ["results"])

        new_value = {
            "value": value,
            "unit": result.unit,
            "spec_status": spec_status,
            "source": source,
        }
        self.audit.record(
            actor,
            AuditAction.RESULT_AMENDED if previous else AuditAction.RESULT_ENTERED,
            entity_type="test_result",
            entity_id=result.id,
            entity_label=label,
            sample_id=sample.id,
            old_value={"value": previous.value, "spec_status": previous.spec_status}
            if previous
            else None,
            new_value=new_value,
            reason=change_reason if previous else None,
        )
        if spec_status == SpecStatus.OOS:
            logger.warning("Resultado OOS: %s = %s %s", label, value, result.unit)
        return result
