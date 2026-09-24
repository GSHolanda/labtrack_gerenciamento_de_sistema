"""Relatório da amostra: montagem do conteúdo, emissão do PDF e registro no audit trail."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.exceptions import NotFoundError
from app.domain.audit import AuditAction
from app.domain.report import content_fingerprint, ensure_reportable, report_filename
from app.models import User
from app.repositories.audit_repository import AuditRepository
from app.repositories.sample_repository import SampleRepository
from app.schemas.common import UserReference
from app.schemas.reports import SampleReport, fingerprint_content, to_report_body
from app.services.audit_service import AuditService, actor_of
from app.services.report_pdf import render_sample_report


@dataclass(frozen=True)
class RenderedReport:
    filename: str
    content: bytes
    content_hash: str
    emission_id: int


class ReportService:
    def __init__(self, session: Session, *, lab_name: str, timezone: str) -> None:
        self.session = session
        self.samples = SampleRepository(session)
        self.audit_log = AuditRepository(session)
        self.audit = AuditService(session)
        self.lab_name = lab_name
        self.timezone = timezone

    def sample_report(self, sample_id: int, actor: User) -> SampleReport:
        """Conteúdo do relatório (prévia). Consultar não gera registro no audit trail."""
        sample = self.samples.get_detailed(sample_id)
        if sample is None:
            raise NotFoundError(f"Amostra {sample_id} não encontrada.", code="SAMPLE_NOT_FOUND")
        ensure_reportable(sample.status, sample.sample_code)  # RN-27

        cancellations = {
            int(event.entity_id): event
            for event in self.audit_log.sample_events(sample.id, AuditAction.TEST_CANCELLED)
            if event.entity_type == "sample_test"
        }
        body = to_report_body(sample, cancellations)
        return SampleReport(
            lab_name=self.lab_name,
            generated_at=utcnow(),
            generated_by=UserReference(id=actor.id, full_name=actor.full_name),
            timezone=self.timezone,
            content_hash=content_fingerprint(fingerprint_content(body)),
            **body,
        )

    def sample_report_pdf(self, sample_id: int, actor: User) -> RenderedReport:
        """RN-28: cada emissão do PDF é registrada no audit trail com a impressão digital."""
        report = self.sample_report(sample_id, actor)
        sample = report.sample
        emission = self.audit.record(
            actor_of(actor),
            AuditAction.REPORT_GENERATED,
            entity_type="sample",
            entity_id=sample.id,
            entity_label=sample.sample_code,
            sample_id=sample.id,
            new_value={
                "format": "PDF",
                "status": sample.status,
                "content_hash": report.content_hash,
            },
        )
        # O PDF é gerado antes do commit: se a geração falhar, a emissão não é registrada.
        content = render_sample_report(report, emission_id=emission.id)
        self.session.commit()
        return RenderedReport(
            filename=report_filename(sample.sample_code),
            content=content,
            content_hash=report.content_hash,
            emission_id=emission.id,
        )
