"""Relatório da amostra: prévia em JSON e emissão em PDF (auditada)."""

from fastapi import APIRouter, Response

from app.api.deps import AppSettings, DbSession
from app.api.v1.endpoints._common import errors, requires
from app.domain.permissions import Permission
from app.schemas.reports import SampleReport
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Reports"])
Exporter = requires(Permission.REPORT_EXPORT)


def _service(session: DbSession, settings: AppSettings) -> ReportService:
    return ReportService(session, lab_name=settings.lab_name, timezone=settings.lab_timezone)


@router.get(
    "/samples/{sample_id}",
    response_model=SampleReport,
    responses=errors(401, 403, 404, 409),
    summary="Conteúdo do relatório da amostra (prévia)",
    description=(
        "Disponível para amostras aprovadas ou reprovadas (`409 REPORT_NOT_AVAILABLE` nos "
        "demais status). Consultar não gera registro no audit trail."
    ),
)
def sample_report(
    sample_id: int, session: DbSession, settings: AppSettings, actor: Exporter
) -> SampleReport:
    return _service(session, settings).sample_report(sample_id, actor)


@router.get(
    "/samples/{sample_id}/pdf",
    response_class=Response,
    responses={
        200: {"content": {"application/pdf": {}}, "description": "Relatório em PDF"},
        **errors(401, 403, 404, 409),
    },
    summary="Emite o relatório da amostra em PDF",
    description=(
        "Cada emissão gera um registro `REPORT_GENERATED` no audit trail com a impressão "
        "digital (SHA-256) do conteúdo, a mesma impressa no rodapé do PDF e informada no "
        "cabeçalho `X-Report-SHA256`."
    ),
)
def sample_report_pdf(
    sample_id: int, session: DbSession, settings: AppSettings, actor: Exporter
) -> Response:
    rendered = _service(session, settings).sample_report_pdf(sample_id, actor)
    return Response(
        content=rendered.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{rendered.filename}"',
            "Cache-Control": "no-store",
            "X-Report-SHA256": rendered.content_hash,
            "X-Report-Emission": str(rendered.emission_id),
        },
    )
