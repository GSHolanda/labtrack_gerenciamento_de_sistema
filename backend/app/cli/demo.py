"""Dados de demonstração gerados pelos próprios serviços.

Nada é inserido direto nas tabelas: cadastros, amostras, resultados (manuais e de
instrumentos), recusas de integração e revisões passam pelos mesmos casos de uso
da API, com as mesmas validações e o mesmo audit trail. O relógio da aplicação é
fixado no momento de cada evento para distribuir o histórico nas últimas semanas,
sempre em ordem cronológica: a timeline e a cadeia de hashes ficam coerentes.
"""

import random
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from itertools import count

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.cli.admin import ensure_admin
from app.core.clock import frozen_at
from app.core.exceptions import AppError
from app.domain.enums import (
    InstrumentStatus,
    RoleCode,
    SampleOrigin,
    SamplePriority,
    SpecStatus,
)
from app.domain.specification import evaluate
from app.models import Client, Instrument, Product, Sample, SampleTest, TestDefinition, User
from app.repositories.user_repository import UserRepository
from app.schemas.instruments import InstrumentCreate, InstrumentUpdate
from app.schemas.master_data import (
    ClientCreate,
    ProductCreate,
    SpecificationItem,
    TestDefinitionCreate,
)
from app.schemas.results import ResultEntry
from app.schemas.samples import SampleCreate
from app.schemas.users import UserCreate
from app.services.instrument_integration_service import InstrumentIntegrationService
from app.services.instrument_service import InstrumentService
from app.services.master_data_service import MasterDataService
from app.services.result_service import ResultService
from app.services.sample_service import SampleService
from app.services.user_service import UserService

ADMIN = ("admin", "admin@labtrack.dev", "Administrador do Sistema")
USERS = [
    ("carlos.silva", "Carlos Silva", RoleCode.ANALYST),
    ("juliana.costa", "Juliana Costa", RoleCode.ANALYST),
    ("ana.souza", "Ana Souza", RoleCode.REVIEWER),
    ("marcos.lima", "Marcos Lima", RoleCode.MANAGER),
]
REVIEWER, MANAGER = "ana.souza", "marcos.lima"

CLIENTS = [
    ("CLI-AURORA", "Farmacêutica Aurora", "qualidade@aurora.example.com"),
    ("CLI-BELLA", "Bella Pele Cosméticos", "lab@bellapele.example.com"),
    ("CLI-VIDA", "Hospital Vida Nova", "farmacia@vidanova.example.com"),
    ("CLI-NORTE", "Distribuidora Norte Saúde", "compras@nortesaude.example.com"),
]

TESTS = [
    TestDefinitionCreate(
        code="PH", name="pH", unit="pH", spec_min=Decimal("4.5"), spec_max=Decimal("8.0"),
        method="Potenciometria", instrument_type="PH_METER", decimal_places=2,
    ),
    TestDefinitionCreate(
        code="DENSITY", name="Densidade", unit="g/mL", spec_min=Decimal("0.950"),
        spec_max=Decimal("1.100"), method="Densímetro digital", instrument_type="DENSITY_METER",
        decimal_places=3,
    ),
    TestDefinitionCreate(
        code="MOISTURE", name="Umidade", unit="%", spec_max=Decimal("1.0"),
        method="Titulação Karl Fischer", instrument_type="MOISTURE_ANALYZER", decimal_places=2,
    ),
    TestDefinitionCreate(
        code="VISCOSITY", name="Viscosidade", unit="mPa·s", spec_min=Decimal(2000),
        spec_max=Decimal(8000), method="Viscosímetro rotacional", instrument_type="VISCOMETER",
        decimal_places=0,
    ),
    TestDefinitionCreate(
        code="ASSAY", name="Teor do ativo", unit="%", spec_min=Decimal("95.0"),
        spec_max=Decimal("105.0"), method="Cromatografia líquida (HPLC-UV)",
        instrument_type="HPLC", decimal_places=1,
    ),
    TestDefinitionCreate(
        code="CONDUCTIVITY", name="Condutividade", unit="mS/cm", spec_min=Decimal("14.00"),
        spec_max=Decimal("17.00"), method="Condutivimetria",
        instrument_type="CONDUCTIVITY_METER", decimal_places=2,
    ),
    TestDefinitionCreate(
        code="AVG_WEIGHT", name="Peso médio", unit="mg", spec_min=Decimal(570),
        spec_max=Decimal(630), method="Gravimetria (20 unidades)", instrument_type="BALANCE",
        decimal_places=1,
    ),
    TestDefinitionCreate(
        code="MICRO_COUNT", name="Contagem microbiana total", unit="UFC/g",
        spec_max=Decimal(100), method="Contagem em placa", decimal_places=0,
    ),
]  # fmt: skip

# código, nome, categoria, plano analítico: (teste, mínimo do produto, máximo do produto)
PRODUCTS = [
    (
        "PRD-SHAMPOO",
        "Xampu Neutro 500 mL",
        "Cosmético",
        [
            ("PH", "5.5", "7.0"),
            ("VISCOSITY", "3000", "6000"),
            ("DENSITY", "1.000", "1.050"),
            ("MICRO_COUNT", None, None),
        ],
    ),
    (
        "PRD-CREAM",
        "Creme Hidratante 200 g",
        "Cosmético",
        [("PH", "5.0", "6.5"), ("VISCOSITY", "5000", "8000"), ("MICRO_COUNT", None, None)],
    ),
    (
        "PRD-DIPYRONE",
        "Dipirona Sódica 500 mg (comprimido)",
        "Medicamento",
        [("ASSAY", None, None), ("MOISTURE", "4.0", "5.5"), ("AVG_WEIGHT", None, None)],
    ),
    (
        "PRD-SALINE",
        "Solução Fisiológica 0,9%",
        "Medicamento",
        [("PH", "4.5", "7.0"), ("CONDUCTIVITY", "14.50", "16.50"), ("DENSITY", "1.000", "1.010")],
    ),
    (
        "PRD-VITC",
        "Vitamina C Efervescente 1 g",
        "Suplemento",
        [("ASSAY", "90.0", "110.0"), ("MOISTURE", None, "0.5"), ("AVG_WEIGHT", "3800", "4200")],
    ),
]

# Cadastro dos equipamentos; "calibration_in_days" é relativo à data da geração.
PHYSCHEM_ROOM = "Sala 2 — Físico-química"
INSTRUMENTS = [
    {
        "code": "PH-METER-01", "name": "pHmetro de bancada", "instrument_type": "PH_METER",
        "manufacturer": "Metrohm", "model": "913", "serial_number": "MH-913-0412",
        "location": PHYSCHEM_ROOM, "calibration_in_days": 150,
    },
    {
        "code": "PH-METER-02", "name": "pHmetro portátil", "instrument_type": "PH_METER",
        "manufacturer": "Mettler Toledo", "model": "Seven2Go", "serial_number": "MT-S2G-7781",
        "location": PHYSCHEM_ROOM, "calibration_in_days": 90,
    },
    {
        "code": "DENS-01", "name": "Densímetro digital", "instrument_type": "DENSITY_METER",
        "manufacturer": "Anton Paar", "model": "DMA 4500", "serial_number": "AP-4500-1190",
        "location": PHYSCHEM_ROOM, "calibration_in_days": 200,
    },
    {
        "code": "KF-01", "name": "Titulador Karl Fischer", "instrument_type": "MOISTURE_ANALYZER",
        "manufacturer": "Metrohm", "model": "Titrando 852", "serial_number": "MH-852-0077",
        "location": "Sala 3 — Umidade", "calibration_in_days": 60,
    },
    {
        "code": "HPLC-01", "name": "Cromatógrafo líquido", "instrument_type": "HPLC",
        "manufacturer": "Agilent", "model": "1260 Infinity II", "serial_number": "AG-1260-5521",
        "location": "Sala 4 — Cromatografia", "calibration_in_days": 120,
    },
    {
        # Calibração vencida há 12 dias: leituras recentes são recusadas (RN-20).
        "code": "VISC-01", "name": "Viscosímetro rotacional", "instrument_type": "VISCOMETER",
        "manufacturer": "Brookfield", "model": "DV2T", "serial_number": "BF-DV2T-3308",
        "location": PHYSCHEM_ROOM, "calibration_in_days": -12,
    },
]  # fmt: skip

PH_METER_MAINTENANCE_DAYS_AGO = 20
HPLC_KEY_ROTATION_DAYS_AGO = 30


@dataclass(frozen=True)
class DemoSample:
    product: str
    client: str
    lot: str
    analyst: str
    days_ago: float
    outcome: str  # received, cancelled, in_analysis, awaiting, approved, rejected
    priority: SamplePriority = SamplePriority.NORMAL
    origin: SampleOrigin = SampleOrigin.PRODUCTION
    # Valor inicial por teste: "in" (padrão), "near_high", "high", "low" ou "typo" (x10).
    kinds: dict[str, str] = field(default_factory=dict)
    pending: tuple[str, ...] = ()  # testes deixados para o simulador ou para o analista
    # Incidentes de integração: "unit:TESTE", "duplicate:TESTE", "early:TESTE", "maintenance:TESTE".
    incidents: tuple[str, ...] = ()
    correction: tuple[str, str] | None = None  # (teste, justificativa) antes do envio
    returned: tuple[str, str, str] | None = None  # (motivo da devolução, teste, justificativa)
    review_reason: str | None = None
    notes: str | None = None


SAMPLES = [
    DemoSample(
        "PRD-SHAMPOO",
        "CLI-BELLA",
        "XN-2608-01",
        "carlos.silva",
        44,
        "approved",
        incidents=("duplicate:PH",),
    ),
    DemoSample(
        "PRD-DIPYRONE",
        "CLI-AURORA",
        "DP-2608-14",
        "juliana.costa",
        42,
        "approved",
        priority=SamplePriority.HIGH,
        incidents=("early:ASSAY",),
    ),
    DemoSample(
        "PRD-SALINE",
        "CLI-VIDA",
        "SF-2608-03",
        "carlos.silva",
        40,
        "approved",
        priority=SamplePriority.URGENT,
        origin=SampleOrigin.CUSTOMER,
        incidents=("unit:DENSITY",),
        notes="Reclamação de cliente: turvação no frasco.",
    ),
    DemoSample(
        "PRD-CREAM",
        "CLI-BELLA",
        "CH-2608-22",
        "juliana.costa",
        38,
        "rejected",
        kinds={"PH": "high"},
        review_reason="pH acima da especificação. Lote reprovado e enviado para "
        "investigação de desvio.",
    ),
    DemoSample(
        "PRD-VITC",
        "CLI-NORTE",
        "VC-2608-09",
        "carlos.silva",
        35,
        "approved",
        kinds={"ASSAY": "low"},
        correction=(
            "ASSAY",
            "Reanálise: erro na diluição do padrão; nova injeção "
            "no HPLC-01 dentro da especificação.",
        ),
    ),
    DemoSample(
        "PRD-SHAMPOO",
        "CLI-BELLA",
        "XN-2608-02",
        "juliana.costa",
        33,
        "approved",
        priority=SamplePriority.LOW,
    ),
    DemoSample(
        "PRD-DIPYRONE",
        "CLI-AURORA",
        "DP-2609-02",
        "carlos.silva",
        30,
        "approved",
        kinds={"MOISTURE": "near_high"},
        returned=(
            "Umidade próxima do limite superior: confirmar com nova determinação em duplicata.",
            "MOISTURE",
            "Nova determinação em duplicata; registrada a média.",
        ),
    ),
    DemoSample(
        "PRD-SALINE",
        "CLI-VIDA",
        "SF-2609-05",
        "juliana.costa",
        28,
        "approved",
        priority=SamplePriority.HIGH,
    ),
    DemoSample("PRD-CREAM", "CLI-BELLA", "CH-2609-01", "carlos.silva", 25, "cancelled"),
    DemoSample(
        "PRD-VITC",
        "CLI-NORTE",
        "VC-2609-04",
        "juliana.costa",
        22,
        "rejected",
        origin=SampleOrigin.STABILITY,
        kinds={"MOISTURE": "high"},
        review_reason="Umidade fora da especificação no estudo de estabilidade "
        "(6 meses). Lote reprovado.",
    ),
    DemoSample("PRD-SHAMPOO", "CLI-BELLA", "XN-2609-03", "carlos.silva", 19, "approved"),
    DemoSample(
        "PRD-DIPYRONE",
        "CLI-AURORA",
        "DP-2609-11",
        "juliana.costa",
        16,
        "approved",
        priority=SamplePriority.URGENT,
        kinds={"AVG_WEIGHT": "typo"},
        correction=("AVG_WEIGHT", "Erro de transcrição: vírgula decimal omitida no lançamento."),
    ),
    DemoSample(
        "PRD-SALINE",
        "CLI-VIDA",
        "SF-2609-12",
        "carlos.silva",
        12,
        "approved",
        incidents=("maintenance:PH",),
    ),
    DemoSample(
        "PRD-CREAM",
        "CLI-BELLA",
        "CH-2609-10",
        "juliana.costa",
        9,
        "awaiting",
        priority=SamplePriority.HIGH,
    ),
    DemoSample(
        "PRD-VITC",
        "CLI-NORTE",
        "VC-2609-15",
        "carlos.silva",
        6,
        "awaiting",
        kinds={"ASSAY": "high"},
    ),
    DemoSample("PRD-SHAMPOO", "CLI-BELLA", "XN-2609-18", "juliana.costa", 4, "awaiting"),
    DemoSample(
        "PRD-DIPYRONE",
        "CLI-AURORA",
        "DP-2609-20",
        "carlos.silva",
        3,
        "in_analysis",
        priority=SamplePriority.HIGH,
        pending=("ASSAY", "MOISTURE"),
    ),
    DemoSample(
        "PRD-SALINE",
        "CLI-VIDA",
        "SF-2609-21",
        "juliana.costa",
        2,
        "in_analysis",
        priority=SamplePriority.URGENT,
        pending=("PH", "DENSITY"),
    ),
    DemoSample(
        "PRD-SHAMPOO",
        "CLI-BELLA",
        "XN-2609-22",
        "carlos.silva",
        1,
        "in_analysis",
        pending=("PH", "VISCOSITY", "DENSITY", "MICRO_COUNT"),
    ),
    DemoSample("PRD-CREAM", "CLI-BELLA", "CH-2609-23", "juliana.costa", 0.3, "received"),
]


class DemoDataError(Exception):
    pass


@dataclass
class DemoSummary:
    password: str
    admin_created: bool
    users: list[tuple[str, str]]  # (usuário, perfil)
    samples_by_status: dict[str, int]
    instrument_keys: dict[str, str]
    rejected_messages: dict[str, int]


Action = Callable[[], None]


def seed_demo(session: Session, password: str, *, now: datetime | None = None) -> DemoSummary:
    """Popula um banco vazio. ``now`` é o fim do histórico (padrão: agora)."""
    return _DemoBuilder(session, password, now or datetime.now(UTC)).build()


class _DemoBuilder:
    def __init__(self, session: Session, password: str, now: datetime) -> None:
        self.session = session
        self.password = password
        self.now = now.astimezone(UTC)
        self.rng = random.Random(2026)
        self.events: list[tuple[datetime, int, Action]] = []
        self.sequence = count()
        self.ids: dict[str, int] = {}  # código/usuário → id
        self.samples: dict[int, int] = {}  # posição em SAMPLES → id da amostra
        self.keys: dict[str, str] = {}
        self.rejections: Counter[str] = Counter()
        self.admin_created = False

    # --- Orquestração ---------------------------------------------------------

    def build(self) -> DemoSummary:
        self._ensure_empty()
        self._at(self._day(50, 9), self._setup)
        self._at(self._day(HPLC_KEY_ROTATION_DAYS_AGO, 16), self._rotate_hplc_key)
        self._at(self._day(PH_METER_MAINTENANCE_DAYS_AGO, 14), self._ph_meter_maintenance)
        for index, spec in enumerate(SAMPLES):
            self._plan(index, spec)

        for moment, _, action in sorted(self.events, key=lambda event: event[:2]):
            if moment > self.now:
                raise DemoDataError(f"Evento de demonstração no futuro: {moment.isoformat()}")
            with frozen_at(moment):
                action()
        self._heartbeats()
        return self._summary()

    def _at(self, moment: datetime, action: Action) -> None:
        self.events.append((moment, next(self.sequence), action))

    def _day(self, days_ago: float, hour: int) -> datetime:
        """Horário de expediente ``days_ago`` dias atrás; menos de um dia: horário exato."""
        moment = self.now - timedelta(days=days_ago)
        if days_ago < 1:
            return moment
        return datetime.combine(moment.date(), time(hour), UTC)

    def _ensure_empty(self) -> None:
        occupied = [
            label
            for label, model in (
                ("amostras", Sample),
                ("clientes", Client),
                ("produtos", Product),
                ("tipos de teste", TestDefinition),
                ("equipamentos", Instrument),
            )
            if self.session.scalar(select(func.count()).select_from(model))
        ]
        users = UserRepository(self.session)
        occupied += [f"usuário {name}" for name, _, _ in USERS if users.find_by_username(name)]
        if occupied:
            raise DemoDataError(
                "O banco já contém dados (" + ", ".join(occupied) + "). "
                "Gere a demonstração em um banco novo."
            )

    # --- Cadastros ------------------------------------------------------------

    def _setup(self) -> None:
        minute = count()

        def step() -> AbstractContextManager[None]:
            return frozen_at(self._day(50, 9) + timedelta(minutes=next(minute)))

        with step():
            admin, self.admin_created = ensure_admin(self.session, *ADMIN, self.password)
        self.ids["admin"] = admin.id
        for username, full_name, role in USERS:
            with step():
                user = UserService(self.session).create(
                    UserCreate(
                        username=username,
                        email=f"{username}@labtrack.dev",
                        full_name=full_name,
                        password=self.password,
                        role=role,
                    ),
                    admin,
                )
            self.ids[username] = user.id

        master_data = MasterDataService(self.session)
        for code, name, email in CLIENTS:
            with step():
                client = master_data.create_client(
                    ClientCreate(code=code, name=name, contact_email=email), admin
                )
            self.ids[code] = client.id
        for definition in TESTS:
            with step():
                created = master_data.create_test_definition(definition, admin)
            self.ids[created.code] = created.id
        for code, name, category, plan in PRODUCTS:
            with step():
                product = master_data.create_product(
                    ProductCreate(code=code, name=name, category=category), admin
                )
                master_data.replace_specifications(
                    product.id,
                    [
                        SpecificationItem(
                            test_definition_id=self.ids[test],
                            spec_min=_decimal(spec_min),
                            spec_max=_decimal(spec_max),
                        )
                        for test, spec_min, spec_max in plan
                    ],
                    admin,
                )
            self.ids[code] = product.id
        for fields in INSTRUMENTS:
            data = {name: value for name, value in fields.items() if name != "calibration_in_days"}
            due = self.now.date() + timedelta(days=int(fields["calibration_in_days"]))
            with step():
                issued = InstrumentService(self.session).create(
                    InstrumentCreate(**data, calibration_due_date=due), admin
                )
            self.ids[issued.instrument.code] = issued.instrument.id
            self.keys[issued.instrument.code] = issued.api_key

    def _rotate_hplc_key(self) -> None:
        issued = InstrumentService(self.session).rotate_key(
            self.ids["HPLC-01"], "Rotação periódica da chave de integração.", self._user("admin")
        )
        self.keys["HPLC-01"] = issued.api_key

    def _ph_meter_maintenance(self) -> None:
        InstrumentService(self.session).update(
            self.ids["PH-METER-02"],
            InstrumentUpdate(status=InstrumentStatus.MAINTENANCE, location="Assistência técnica"),
            self._user("admin"),
        )

    # --- Amostras -------------------------------------------------------------

    def _plan(self, index: int, spec: DemoSample) -> None:
        start = self._day(spec.days_ago, 11)

        def at(minutes: int, action: Action) -> None:
            self._at(start + timedelta(minutes=minutes), action)

        at(20, lambda: self._register(index, spec, start))
        if spec.outcome == "received":
            return
        for incident in spec.incidents:
            if incident.startswith("early:"):
                test = incident.split(":")[1]
                at(40, lambda test=test: self._early_attempt(index, test))
        at(60, lambda: self._samples().start_analysis(self._sample_id(index), self._analyst(spec)))
        if spec.outcome == "cancelled":
            at(150, lambda: self._cancel(index))
            return

        minute = 90
        for test, _, _ in _plan_of(spec.product):
            if test not in spec.pending:
                at(minute, lambda test=test: self._measure(index, spec, test))
                minute += 25
        if spec.correction:
            test, reason = spec.correction
            at(minute + 60, lambda: self._correct(index, spec, test, reason))
        if spec.outcome == "in_analysis":
            return

        day = 24 * 60
        at(day + 30, lambda: self._submit_for_review(index, spec))
        if spec.outcome == "awaiting":
            return
        review = 2 * day + 60
        if spec.returned:
            reason, test, amend_reason = spec.returned
            at(review, lambda: self._return(index, reason))
            at(review + 180, lambda: self._correct(index, spec, test, amend_reason))
            at(review + 240, lambda: self._submit_for_review(index, spec))
            review += day
        if spec.outcome == "rejected":
            at(review, lambda: self._reject(index, spec))
        else:
            at(review, lambda: self._approve(index))

    def _register(self, index: int, spec: DemoSample, received_at: datetime) -> None:
        sample = self._samples().create(
            SampleCreate(
                product_id=self.ids[spec.product],
                client_id=self.ids[spec.client],
                lot_number=spec.lot,
                origin=spec.origin,
                received_at=received_at,
                priority=spec.priority,
                responsible_id=self.ids[spec.analyst],
                notes=spec.notes,
            ),
            self._analyst(spec),
        )
        self.samples[index] = sample.id

    def _measure(self, index: int, spec: DemoSample, test: str) -> None:
        sample_test = self._sample_test(index, test)
        value = self._value(sample_test, spec.kinds.get(test, "in"))
        code = sample_test.sample.sample_code
        instrument = self._instrument_for(sample_test.test_definition.instrument_type, index)
        comment = None
        if instrument is not None:
            if f"unit:{test}" in spec.incidents:
                self._send(instrument, code, test, value, "g/cm3")
            if f"maintenance:{test}" in spec.incidents:
                self._send("PH-METER-02", code, test, value, sample_test.unit)
            rejection = self._send(instrument, code, test, value, sample_test.unit)
            if rejection is None:
                if f"duplicate:{test}" in spec.incidents:
                    self._send(instrument, code, test, value, sample_test.unit)
                return
            comment = f"Lançamento manual: o {instrument} recusou a leitura ({rejection})."
        ResultService(self.session).enter_manual(
            sample_test.id, ResultEntry(value=value, comment=comment), self._analyst(spec)
        )

    def _early_attempt(self, index: int, test: str) -> None:
        sample_test = self._sample_test(index, test)
        instrument = self._instrument_for(sample_test.test_definition.instrument_type, index)
        assert instrument is not None
        value = self._value(sample_test, "in")
        self._send(instrument, sample_test.sample.sample_code, test, value, sample_test.unit)

    def _correct(self, index: int, spec: DemoSample, test: str, reason: str) -> None:
        sample_test = self._sample_test(index, test)
        ResultService(self.session).enter_manual(
            sample_test.id,
            ResultEntry(value=self._value(sample_test, "in"), change_reason=reason),
            self._analyst(spec),
        )

    def _submit_for_review(self, index: int, spec: DemoSample) -> None:
        self._samples().submit_for_review(self._sample_id(index), self._analyst(spec))

    def _approve(self, index: int) -> None:
        self._samples().approve(
            self._sample_id(index),
            self.password,
            "Resultados conferidos. Liberado.",
            self._user(REVIEWER),
        )

    def _reject(self, index: int, spec: DemoSample) -> None:
        assert spec.review_reason
        self._samples().reject(self._sample_id(index), spec.review_reason, self._user(REVIEWER))

    def _return(self, index: int, reason: str) -> None:
        self._samples().return_to_analysis(self._sample_id(index), reason, self._user(REVIEWER))

    def _cancel(self, index: int) -> None:
        self._samples().cancel(
            self._sample_id(index),
            "Amostra registrada em duplicidade: o lote já está em outra amostra.",
            self._user(MANAGER),
        )

    # --- Integração -----------------------------------------------------------

    def _instrument_for(self, instrument_type: str | None, index: int) -> str | None:
        candidates = [
            str(item["code"]) for item in INSTRUMENTS if item["instrument_type"] == instrument_type
        ]
        if not candidates:
            return None
        active = [
            code
            for code in candidates
            if self.session.get(Instrument, self.ids[code]).status == InstrumentStatus.ACTIVE
        ]
        options = active or candidates
        return options[index % len(options)]

    def _send(
        self, instrument: str, sample_code: str, test: str, value: Decimal, unit: str
    ) -> str | None:
        """Envia como o equipamento faria. Retorna o código da recusa, se houver."""
        payload = {
            "instrument_id": instrument,
            "sample_code": sample_code,
            "test": test,
            "result": str(value),
            "unit": unit,
        }
        try:
            InstrumentIntegrationService(self.session).submit_result(
                self.session.get(Instrument, self.ids[instrument]), payload
            )
        except AppError as error:
            self.rejections[error.code] += 1
            return error.code
        return None

    def _heartbeats(self) -> None:
        """Relógio real: equipamentos em uso aparecem online ao fim da geração."""
        service = InstrumentIntegrationService(self.session)
        for item in INSTRUMENTS:
            if item["code"] != "PH-METER-02":
                service.heartbeat(self.session.get(Instrument, self.ids[str(item["code"])]), None)

    # --- Auxiliares -----------------------------------------------------------

    def _value(self, sample_test: SampleTest, kind: str) -> Decimal:
        """Valor coerente com a especificação do teste e com o cenário desejado."""
        spec_min, spec_max = sample_test.spec_min, sample_test.spec_max
        high = float(spec_max) if spec_max is not None else float(spec_min) * 1.2
        low = float(spec_min) if spec_min is not None else high * 0.2
        width = high - low
        if kind == "high":
            number = high + width * self.rng.uniform(0.08, 0.25)
        elif kind == "low":
            number = low - width * self.rng.uniform(0.08, 0.25)
        elif kind == "near_high":
            number = high - width * 0.03
        else:
            number = self.rng.uniform(low + width * 0.2, high - width * 0.2)
            if kind == "typo":
                number *= 10
        places = sample_test.test_definition.decimal_places
        value = Decimal(repr(number)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
        expected = SpecStatus.IN_SPEC if kind in ("in", "near_high") else SpecStatus.OOS
        if evaluate(value, spec_min, spec_max) != expected:
            raise DemoDataError(f"Valor {value} não representa o cenário '{kind}'.")
        return value

    def _samples(self) -> SampleService:
        return SampleService(self.session)

    def _sample_id(self, index: int) -> int:
        return self.samples[index]

    def _sample_test(self, index: int, test: str) -> SampleTest:
        sample = self._samples().get(self._sample_id(index))
        return next(t for t in sample.tests if t.test_definition.code == test)

    def _user(self, username: str) -> User:
        user = self.session.get(User, self.ids[username])
        assert user is not None
        return user

    def _analyst(self, spec: DemoSample) -> User:
        return self._user(spec.analyst)

    def _summary(self) -> DemoSummary:
        statuses = Counter(self.session.scalars(select(Sample.status)))
        return DemoSummary(
            password=self.password,
            admin_created=self.admin_created,
            users=[(ADMIN[0], RoleCode.ADMIN.value)]
            + [(name, role.value) for name, _, role in USERS],
            samples_by_status=dict(sorted(statuses.items())),
            instrument_keys=dict(self.keys),
            rejected_messages=dict(sorted(self.rejections.items())),
        )


def _plan_of(product: str) -> list[tuple[str, str | None, str | None]]:
    return next(plan for code, _, _, plan in PRODUCTS if code == product)


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
