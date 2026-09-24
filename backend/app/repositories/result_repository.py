from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app.domain.pagination import PageRequest, PageResult
from app.models import Sample, SampleTest, TestDefinition, TestResult
from app.repositories.base import BaseRepository
from app.schemas.results import ResultFilter


class ResultRepository(BaseRepository[TestResult]):
    model = TestResult
    sortable = {  # noqa: RUF012
        "entered_at": TestResult.entered_at,
        "value": TestResult.value,
        "sample_code": Sample.sample_code,
        "test_code": TestDefinition.code,
    }
    default_sort = (TestResult.entered_at.desc(),)

    def history(self, sample_test_id: int) -> list[TestResult]:
        return list(
            self.session.scalars(
                select(TestResult)
                .where(TestResult.sample_test_id == sample_test_id)
                .options(selectinload(TestResult.entered_by), selectinload(TestResult.instrument))
                .order_by(TestResult.version)
            )
        )

    def search(self, filters: ResultFilter, page: PageRequest) -> PageResult[TestResult]:
        statement = (
            select(TestResult)
            .join(TestResult.sample_test)
            .join(SampleTest.sample)
            .join(SampleTest.test_definition)
            .options(
                joinedload(TestResult.sample_test).joinedload(SampleTest.sample),
                selectinload(TestResult.entered_by),
                selectinload(TestResult.instrument),
            )
        )
        if filters.current_only:
            statement = statement.where(TestResult.is_current.is_(True))
        if filters.spec_status:
            statement = statement.where(TestResult.spec_status == filters.spec_status)
        if filters.source:
            statement = statement.where(TestResult.source == filters.source)
        if filters.test_code:
            statement = statement.where(TestDefinition.code == filters.test_code.upper())
        if filters.sample_code:
            statement = statement.where(Sample.sample_code.ilike(f"%{filters.sample_code}%"))
        if filters.entered_from:
            statement = statement.where(TestResult.entered_at >= filters.entered_from)
        if filters.entered_to:
            statement = statement.where(TestResult.entered_at <= filters.entered_to)
        return self.paginate(statement, page)
