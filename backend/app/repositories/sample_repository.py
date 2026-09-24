from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import contains_eager, selectinload

from app.domain.enums import SampleStatus, SampleTestStatus
from app.domain.instruments import PRIORITY_RANK
from app.domain.pagination import PageRequest, PageResult
from app.domain.sample_code import parse_sequence, year_prefix
from app.models import (
    Client,
    Product,
    Sample,
    SampleStatusHistory,
    SampleTest,
    TestDefinition,
    TestResult,
)
from app.repositories.base import BaseRepository
from app.schemas.samples import SampleFilter

_SAMPLE_CODE_LOCK_KEY = 7_415_002


class SampleRepository(BaseRepository[Sample]):
    model = Sample
    sortable = {  # noqa: RUF012
        "sample_code": Sample.sample_code,
        "received_at": Sample.received_at,
        "priority": Sample.priority,
        "status": Sample.status,
        "lot_number": Sample.lot_number,
    }
    default_sort = (Sample.received_at.desc(),)

    def get_detailed(self, sample_id: int) -> Sample | None:
        return self.session.scalar(
            select(Sample)
            .where(Sample.id == sample_id)
            .options(
                selectinload(Sample.tests).selectinload(SampleTest.test_definition),
                selectinload(Sample.tests)
                .selectinload(SampleTest.results)
                .selectinload(TestResult.entered_by),
                selectinload(Sample.tests)
                .selectinload(SampleTest.results)
                .selectinload(TestResult.instrument),
                selectinload(Sample.responsible),
                selectinload(Sample.created_by),
                selectinload(Sample.reviewed_by),
            )
        )

    def id_by_code(self, sample_code: str) -> int | None:
        return self.session.scalar(select(Sample.id).where(Sample.sample_code == sample_code))

    def find_by_code_for_update(self, sample_code: str) -> Sample | None:
        """Carrega a amostra bloqueando a linha até o fim da transação (PostgreSQL).

        Serializa resultados simultâneos de instrumentos e transições de status da
        mesma amostra: quem chega depois relê o estado já confirmado.
        """
        return self.session.scalar(
            select(Sample)
            .where(Sample.sample_code == sample_code.upper())
            .with_for_update(of=Sample)
            .execution_options(populate_existing=True)
        )

    def next_sequence(self, year: int) -> int:
        """Próximo sequencial do ano. No PostgreSQL, serializado por advisory lock."""
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(:key, :year)"),
                {"key": _SAMPLE_CODE_LOCK_KEY, "year": year},
            )
        codes = self.session.scalars(
            select(Sample.sample_code).where(Sample.sample_code.like(f"{year_prefix(year)}%"))
        )
        return max((parse_sequence(code) or 0 for code in codes), default=0) + 1

    def search(self, filters: SampleFilter, page: PageRequest) -> PageResult[Sample]:
        statement = (
            select(Sample)
            .join(Sample.product)
            .join(Sample.client)
            .options(selectinload(Sample.responsible))
        )
        if filters.code:
            statement = statement.where(Sample.sample_code.ilike(f"%{filters.code}%"))
        if filters.product_id:
            statement = statement.where(Sample.product_id == filters.product_id)
        if filters.client_id:
            statement = statement.where(Sample.client_id == filters.client_id)
        if filters.lot_number:
            statement = statement.where(Sample.lot_number.ilike(f"%{filters.lot_number}%"))
        if filters.statuses:
            statement = statement.where(Sample.status.in_(filters.statuses))
        if filters.priority:
            statement = statement.where(Sample.priority == filters.priority)
        if filters.responsible_id:
            statement = statement.where(Sample.responsible_id == filters.responsible_id)
        if filters.received_from:
            statement = statement.where(Sample.received_at >= filters.received_from)
        if filters.received_to:
            statement = statement.where(Sample.received_at <= filters.received_to)
        if filters.q:
            pattern = f"%{filters.q.lower()}%"
            statement = statement.where(
                or_(
                    func.lower(Sample.sample_code).like(pattern),
                    func.lower(Sample.lot_number).like(pattern),
                    func.lower(Product.name).like(pattern),
                    func.lower(Client.name).like(pattern),
                )
            )
        return self.paginate(statement, page)

    def status_history(self, sample_id: int) -> list[SampleStatusHistory]:
        return list(
            self.session.scalars(
                select(SampleStatusHistory)
                .where(SampleStatusHistory.sample_id == sample_id)
                .options(selectinload(SampleStatusHistory.changed_by))
                .order_by(SampleStatusHistory.changed_at, SampleStatusHistory.id)
            )
        )


class SampleTestRepository(BaseRepository[SampleTest]):
    model = SampleTest

    def find_in_sample(self, sample_id: int, test_code: str) -> SampleTest | None:
        return self.session.scalar(
            select(SampleTest)
            .join(SampleTest.test_definition)
            .where(SampleTest.sample_id == sample_id, TestDefinition.code == test_code.upper())
            .execution_options(populate_existing=True)
        )

    def pending_for_instrument_type(self, instrument_type: str, limit: int) -> list[SampleTest]:
        """Worklist: testes pendentes, em amostras em análise, que o tipo de equipamento executa."""
        priority = case(PRIORITY_RANK, value=Sample.priority, else_=len(PRIORITY_RANK))
        return list(
            self.session.scalars(
                select(SampleTest)
                .join(SampleTest.sample)
                .join(SampleTest.test_definition)
                .where(
                    Sample.status == SampleStatus.IN_ANALYSIS,
                    SampleTest.status == SampleTestStatus.PENDING,
                    TestDefinition.instrument_type == instrument_type,
                )
                .options(contains_eager(SampleTest.sample))
                .order_by(priority, Sample.received_at, SampleTest.id)
                .limit(limit)
            ).unique()
        )
