"""O banco é a última linha de defesa: estas regras valem mesmo se a aplicação falhar."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.database.session import build_session_factory
from app.domain.enums import ResultSource, SampleStatus, SpecStatus
from app.models import Sample, TestDefinition, TestResult

from .conftest import LabData

EXPECTED_TABLES = {
    "roles",
    "users",
    "clients",
    "products",
    "test_definitions",
    "product_specifications",
    "instruments",
    "samples",
    "sample_status_history",
    "sample_tests",
    "test_results",
    "instrument_results",
    "audit_logs",
}


def _result(lab: LabData, **overrides: object) -> TestResult:
    fields: dict[str, object] = {
        "sample_test_id": lab.sample_test.id,
        "value": Decimal("7.2"),
        "unit": "pH",
        "spec_status": SpecStatus.IN_SPEC,
        "source": ResultSource.MANUAL,
        "entered_by_id": lab.analyst.id,
    }
    fields.update(overrides)
    return TestResult(**fields)


def _assert_rejected(session: Session, *objects: object) -> None:
    session.add_all(objects)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_schema_has_all_tables(engine: Engine) -> None:
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES


def test_valid_result_is_accepted_with_exact_decimal(session: Session, lab: LabData) -> None:
    session.add(_result(lab, value=Decimal("7.5000")))
    session.commit()

    stored = session.scalars(select(TestResult)).one()
    assert stored.value == Decimal("7.5")
    assert stored.version == 1
    assert stored.is_current is True


def test_result_must_be_attributable_to_user_or_instrument(session: Session, lab: LabData) -> None:
    _assert_rejected(session, _result(lab, entered_by_id=None))
    _assert_rejected(session, _result(lab, source=ResultSource.INSTRUMENT, entered_by_id=None))


def test_instrument_result_is_attributable_to_instrument(session: Session, lab: LabData) -> None:
    session.add(
        _result(
            lab, source=ResultSource.INSTRUMENT, entered_by_id=None, instrument_id=lab.instrument.id
        )
    )
    session.commit()


def test_amended_result_requires_reason(session: Session, lab: LabData) -> None:
    session.add(_result(lab, is_current=False))
    session.flush()

    _assert_rejected(session, _result(lab, version=2))


def test_only_one_current_result_per_test(session: Session, lab: LabData) -> None:
    session.add(_result(lab))
    session.flush()

    _assert_rejected(session, _result(lab, version=2, change_reason="Erro de digitação"))


def test_result_version_history_is_kept(session: Session, lab: LabData) -> None:
    session.add(_result(lab, value=Decimal("7.3"), is_current=False))
    session.add(_result(lab, value=Decimal("7.1"), version=2, change_reason="Erro de digitação"))
    session.commit()

    values = session.scalars(select(TestResult.value).order_by(TestResult.version)).all()
    assert values == [Decimal("7.3"), Decimal("7.1")]


def test_invalid_enum_values_are_rejected(session: Session, lab: LabData) -> None:
    _assert_rejected(session, _result(lab, spec_status="MAYBE"))


@pytest.mark.parametrize(
    ("spec_min", "spec_max"),
    [(Decimal("7.5"), Decimal("6.5")), (None, None)],
    ids=["min-maior-que-max", "sem-limites"],
)
def test_test_definition_requires_consistent_limits(
    session: Session, spec_min: Decimal | None, spec_max: Decimal | None
) -> None:
    definition = TestDefinition(
        code="X", name="X", unit="u", spec_min=spec_min, spec_max=spec_max, method="m"
    )
    _assert_rejected(session, definition)


def test_final_sample_requires_reviewer(session: Session, lab: LabData) -> None:
    lab.sample.status = SampleStatus.APPROVED
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

    sample = session.get(Sample, lab.sample.id)
    assert sample is not None
    sample.status = SampleStatus.APPROVED
    sample.reviewed_by_id = lab.analyst.id
    sample.reviewed_at = datetime.now(UTC)
    session.commit()


def test_sample_code_is_unique(session: Session, lab: LabData) -> None:
    duplicate = Sample(
        sample_code=lab.sample.sample_code,
        product_id=lab.sample.product_id,
        client_id=lab.sample.client_id,
        lot_number="L2",
        origin="PRODUCTION",
        received_at=datetime.now(UTC),
        created_by_id=lab.analyst.id,
    )
    _assert_rejected(session, duplicate)


def test_optimistic_locking_detects_concurrent_update(engine: Engine, lab: LabData) -> None:
    factory = build_session_factory(engine)
    with factory() as first, factory() as second:
        sample_a = first.get(Sample, lab.sample.id)
        sample_b = second.get(Sample, lab.sample.id)
        assert sample_a is not None and sample_b is not None

        sample_a.notes = "Alteração do analista A"
        first.commit()
        assert sample_a.version == 2

        sample_b.notes = "Alteração do analista B, baseada em dados antigos"
        with pytest.raises(StaleDataError):
            second.commit()
