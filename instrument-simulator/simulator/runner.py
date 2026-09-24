"""Ciclo de trabalho de um equipamento: heartbeat, worklist, medição e envio."""

import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol

from simulator.client import ApiError
from simulator.measurement import generate_value

Log = Callable[[str], None]


class InstrumentApi(Protocol):
    def worklist(self, limit: int = 50) -> dict: ...

    def submit_result(
        self, instrument_id: str, sample_code: str, test: str, result: Decimal, unit: str
    ) -> dict: ...

    def heartbeat(self, instrument_id: str) -> dict: ...


@dataclass
class CycleReport:
    instrument: str
    accepted: int = 0
    oos: int = 0
    rejected: list[tuple[str, str, str]] = field(default_factory=list)  # amostra, teste, código
    error: str | None = None  # a worklist não pôde ser lida


class InstrumentSimulator:
    def __init__(
        self,
        code: str,
        api: InstrumentApi,
        *,
        oos_rate: float,
        rng: random.Random,
        max_results: int | None = None,
        log: Log = print,
    ) -> None:
        self.code = code
        self.api = api
        self.oos_rate = oos_rate
        self.rng = rng
        self.max_results = max_results
        self.log = log

    def heartbeat(self) -> None:
        try:
            state = self.api.heartbeat(self.code)
        except ApiError as error:
            self.log(f"[{self.code}] heartbeat recusado: {error.code}: {error.message}")
            return
        if not state["can_measure"]:
            reason = "calibração vencida" if not state["calibration_valid"] else state["status"]
            self.log(f"[{self.code}] conectado, mas sem liberar medições ({reason})")

    def run_cycle(self) -> CycleReport:
        report = CycleReport(self.code)
        try:
            worklist = self.api.worklist()
        except ApiError as error:
            report.error = error.code
            self.log(f"[{self.code}] worklist indisponível: {error.code}: {error.message}")
            return report

        items = worklist["items"][: self.max_results]
        if not items:
            self.log(f"[{self.code}] nenhum teste pendente")
        for item in items:
            self._measure(item, report)
        return report

    def _measure(self, item: dict, report: CycleReport) -> None:
        oos = self.rng.random() < self.oos_rate
        value = generate_value(
            _decimal(item["spec_min"]),
            _decimal(item["spec_max"]),
            item["decimal_places"],
            oos=oos,
            rng=self.rng,
        )
        sample, test, unit = item["sample_code"], item["test"], item["unit"]
        try:
            accepted = self.api.submit_result(self.code, sample, test, value, unit)
        except ApiError as error:
            report.rejected.append((sample, test, error.code))
            message = f" (mensagem {error.message_id})" if error.message_id else ""
            self.log(f"[{self.code}] {sample} {test}: recusado {error.code}{message}")
            return
        report.accepted += 1
        flag = ""
        if accepted["spec_status"] == "OOS":
            report.oos += 1
            flag = "  << OOS"
        self.log(f"[{self.code}] {sample} {test} = {value} {unit}: {accepted['spec_status']}{flag}")


def run(
    simulators: Sequence[InstrumentSimulator],
    *,
    cycles: int | None,
    interval: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[CycleReport]:
    """Executa os equipamentos em sequência a cada ciclo; ``cycles=None`` roda até Ctrl+C."""
    reports: list[CycleReport] = []
    cycle = 0
    while cycles is None or cycle < cycles:
        for simulator in simulators:
            simulator.heartbeat()
            reports.append(simulator.run_cycle())
        cycle += 1
        if cycles is None or cycle < cycles:
            sleep(interval)
    return reports


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value is not None else None
