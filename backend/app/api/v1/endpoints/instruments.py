"""Instrumentos: gestão pelos usuários (JWT) e integração dos equipamentos (X-Instrument-Key)."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Query, status

from app.api.deps import CurrentInstrumentDep, CurrentUserDep, DbSession
from app.api.v1.endpoints._common import Paging, errors, requires
from app.domain.enums import InstrumentMessageStatus, InstrumentStatus, InstrumentType
from app.domain.pagination import MAX_PAGE_SIZE
from app.domain.permissions import Permission
from app.schemas.common import Page
from app.schemas.instruments import (
    HeartbeatRead,
    HeartbeatRequest,
    InstrumentCreate,
    InstrumentFilter,
    InstrumentKeyRead,
    InstrumentMessageFilter,
    InstrumentMessageRead,
    InstrumentRead,
    InstrumentResultAccepted,
    InstrumentResultSubmission,
    InstrumentUpdate,
    KeyRotationRequest,
    Worklist,
    to_accepted,
    to_heartbeat,
    to_instrument,
    to_instrument_with_key,
    to_worklist,
)
from app.services.instrument_integration_service import InstrumentIntegrationService
from app.services.instrument_service import InstrumentService

# Registrado antes do router de gestão: "/instruments/worklist" não pode ser
# capturado por "/instruments/{instrument_id}".
integration_router = APIRouter(prefix="/instruments", tags=["Instrument Integration"])
router = APIRouter(prefix="/instruments", tags=["Instruments"])

Manager = requires(Permission.INSTRUMENT_MANAGE)

# --- Integração ---------------------------------------------------------------


@integration_router.get(
    "/worklist",
    response_model=Worklist,
    responses=errors(401, 409),
    summary="Testes pendentes que este equipamento pode executar",
    description=(
        "Amostras em análise com testes pendentes do tipo do equipamento, das mais "
        "urgentes para as menos urgentes. Equipamento inativo, em manutenção ou com "
        "calibração vencida recebe `409`."
    ),
)
def worklist(
    session: DbSession,
    instrument: CurrentInstrumentDep,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
) -> Worklist:
    items = InstrumentIntegrationService(session).worklist(instrument, limit)
    return to_worklist(instrument, items)


@integration_router.post(
    "/results",
    response_model=InstrumentResultAccepted,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 404, 409, 422),
    summary="Envia um resultado",
    description=(
        "Toda mensagem é registrada no log do equipamento, aceita ou recusada. Na recusa, "
        "nenhum resultado é gravado e `error.details.message_id` identifica a mensagem. "
        "O instrumento nunca sobrescreve resultado: correções são manuais e justificadas."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {"schema": InstrumentResultSubmission.model_json_schema()}
            },
        }
    },
)
def submit_result(
    session: DbSession,
    instrument: CurrentInstrumentDep,
    # Corpo lido sem validação na borda: mensagens malformadas também entram no log (RN-24).
    payload: Annotated[Any, Body()] = None,
) -> InstrumentResultAccepted:
    accepted = InstrumentIntegrationService(session).submit_result(instrument, payload)
    return to_accepted(accepted.message, accepted.result)


@integration_router.post(
    "/heartbeat",
    response_model=HeartbeatRead,
    responses=errors(401, 403),
    summary="Sinaliza que o equipamento está conectado",
    description="Atualiza a última comunicação e informa se o equipamento pode medir.",
)
def heartbeat(
    session: DbSession,
    instrument: CurrentInstrumentDep,
    data: HeartbeatRequest | None = None,
) -> HeartbeatRead:
    code = data.instrument_id if data else None
    return to_heartbeat(InstrumentIntegrationService(session).heartbeat(instrument, code))


# --- Gestão -------------------------------------------------------------------


@router.get("", response_model=Page[InstrumentRead], summary="Equipamentos e última comunicação")
def list_instruments(
    session: DbSession,
    _: CurrentUserDep,
    paging: Paging,
    q: Annotated[
        str | None, Query(max_length=100, description="Código, nome, local ou série")
    ] = None,
    status_: Annotated[InstrumentStatus | None, Query(alias="status")] = None,
    instrument_type: InstrumentType | None = None,
) -> Page[InstrumentRead]:
    result = InstrumentService(session).search(
        InstrumentFilter(q=q, status=status_, instrument_type=instrument_type), paging
    )
    return Page.build(
        [to_instrument(item) for item in result.items], result.total, result.page, result.size
    )


@router.post(
    "",
    response_model=InstrumentKeyRead,
    status_code=status.HTTP_201_CREATED,
    responses=errors(401, 403, 409),
    summary="Cadastra equipamento (a chave é exibida uma única vez)",
)
def create_instrument(
    data: InstrumentCreate, session: DbSession, actor: Manager
) -> InstrumentKeyRead:
    issued = InstrumentService(session).create(data, actor)
    return to_instrument_with_key(issued.instrument, issued.api_key)


@router.get("/{instrument_id}", response_model=InstrumentRead, responses=errors(401, 404))
def get_instrument(instrument_id: int, session: DbSession, _: CurrentUserDep) -> InstrumentRead:
    return to_instrument(InstrumentService(session).get(instrument_id))


@router.patch(
    "/{instrument_id}",
    response_model=InstrumentRead,
    responses=errors(401, 403, 404, 409),
    summary="Altera status, calibração, localização e dados cadastrais",
    description="Código e tipo não podem ser alterados. Toda alteração é auditada.",
)
def update_instrument(
    instrument_id: int, data: InstrumentUpdate, session: DbSession, actor: Manager
) -> InstrumentRead:
    return to_instrument(InstrumentService(session).update(instrument_id, data, actor))


@router.post(
    "/{instrument_id}/rotate-key",
    response_model=InstrumentKeyRead,
    responses=errors(401, 403, 404),
    summary="Gera nova chave de integração",
    description="A chave anterior deixa de funcionar imediatamente.",
)
def rotate_key(
    instrument_id: int,
    session: DbSession,
    actor: Manager,
    data: KeyRotationRequest | None = None,
) -> InstrumentKeyRead:
    issued = InstrumentService(session).rotate_key(
        instrument_id, data.reason if data else None, actor
    )
    return to_instrument_with_key(issued.instrument, issued.api_key)


@router.get(
    "/{instrument_id}/messages",
    response_model=Page[InstrumentMessageRead],
    responses=errors(401, 404, 422),
    summary="Log de mensagens recebidas (aceitas e recusadas)",
)
def list_messages(
    instrument_id: int,
    session: DbSession,
    _: CurrentUserDep,
    paging: Paging,
    status_: Annotated[InstrumentMessageStatus | None, Query(alias="status")] = None,
) -> Page[InstrumentMessageRead]:
    result = InstrumentService(session).search_messages(
        instrument_id, InstrumentMessageFilter(status=status_), paging
    )
    return Page.build(
        [InstrumentMessageRead.model_validate(item) for item in result.items],
        result.total,
        result.page,
        result.size,
    )
