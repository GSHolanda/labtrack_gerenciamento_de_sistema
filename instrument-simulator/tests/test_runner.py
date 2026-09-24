import random
from decimal import Decimal

from simulator.client import ApiError
from simulator.runner import InstrumentSimulator, run


class FakeApi:
    def __init__(self, items: list[dict], *, reject: set[str] = frozenset()) -> None:
        self.items = items
        self.reject = reject
        self.sent: list[tuple[str, str, Decimal, str]] = []
        self.heartbeats = 0

    def worklist(self, limit: int = 50) -> dict:
        return {"items": self.items}

    def submit_result(
        self, instrument_id: str, sample_code: str, test: str, result: Decimal, unit: str
    ) -> dict:
        if sample_code in self.reject:
            raise ApiError(409, "TEST_ALREADY_COMPLETED", "já tem resultado", {"message_id": 7})
        self.sent.append((sample_code, test, result, unit))
        in_spec = Decimal("5.5") <= result <= Decimal("7.0")
        return {"spec_status": "IN_SPEC" if in_spec else "OOS"}

    def heartbeat(self, instrument_id: str) -> dict:
        self.heartbeats += 1
        return {"can_measure": True, "calibration_valid": True, "status": "ACTIVE"}


def _item(sample: str) -> dict:
    return {
        "sample_code": sample,
        "test": "PH",
        "unit": "pH",
        "spec_min": "5.5",
        "spec_max": "7.0",
        "decimal_places": 2,
    }


def _simulator(api: FakeApi, oos_rate: float, **kwargs: object) -> InstrumentSimulator:
    logs: list[str] = []
    return InstrumentSimulator(
        "PH-METER-01", api, oos_rate=oos_rate, rng=random.Random(1), log=logs.append, **kwargs
    )


def test_cycle_measures_the_worklist() -> None:
    api = FakeApi([_item("SMP-1"), _item("SMP-2"), _item("SMP-3")], reject={"SMP-2"})

    report = _simulator(api, oos_rate=0).run_cycle()

    assert [sent[0] for sent in api.sent] == ["SMP-1", "SMP-3"]
    assert all(unit == "pH" for *_, unit in api.sent)
    assert (report.accepted, report.oos) == (2, 0)
    assert report.rejected == [("SMP-2", "PH", "TEST_ALREADY_COMPLETED")]


def test_oos_rate_one_sends_only_oos_and_max_results_limits() -> None:
    api = FakeApi([_item(f"SMP-{n}") for n in range(5)])

    report = _simulator(api, oos_rate=1, max_results=3).run_cycle()

    assert len(api.sent) == 3
    assert report.oos == report.accepted == 3


def test_worklist_error_is_reported() -> None:
    class Blocked(FakeApi):
        def worklist(self, limit: int = 50) -> dict:
            raise ApiError(409, "CALIBRATION_EXPIRED", "calibração vencida")

    report = _simulator(Blocked([]), oos_rate=0).run_cycle()
    assert report.error == "CALIBRATION_EXPIRED"


def test_run_repeats_cycles_with_heartbeat_and_interval() -> None:
    api = FakeApi([])
    sleeps: list[float] = []

    reports = run([_simulator(api, oos_rate=0)], cycles=3, interval=2.5, sleep=sleeps.append)

    assert len(reports) == 3
    assert api.heartbeats == 3
    assert sleeps == [2.5, 2.5]
