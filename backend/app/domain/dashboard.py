"""Regras puras do dashboard: janelas de tempo, agrupamento e indicadores."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from enum import StrEnum
from statistics import mean, median

# Até 31 dias a série é diária; até 120, semanal; acima disso, mensal. Assim a
# série tem sempre entre ~7 e ~31 pontos e nunca vira um gráfico mensal vazio.
MAX_DAILY_DAYS = 31
MAX_WEEKLY_DAYS = 120


class Granularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


def granularity_for(period_days: int) -> Granularity:
    if period_days <= MAX_DAILY_DAYS:
        return Granularity.DAY
    if period_days <= MAX_WEEKLY_DAYS:
        return Granularity.WEEK
    return Granularity.MONTH


def as_utc(moment: datetime) -> datetime:
    """SQLite devolve datas sem fuso; todas são UTC."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


@dataclass(frozen=True)
class Window:
    """Intervalo semiaberto [start, end), em UTC."""

    start: datetime
    end: datetime

    @classmethod
    def last_days(cls, days: int, now: datetime) -> "Window":
        end = as_utc(now)
        return cls(end - timedelta(days=days), end)

    def previous(self) -> "Window":
        """Período imediatamente anterior, de mesma duração (base de comparação)."""
        return Window(self.start - (self.end - self.start), self.start)

    def contains(self, moment: datetime) -> bool:
        return self.start <= as_utc(moment) < self.end


def bucket_of(moment: datetime, granularity: Granularity, tz: tzinfo) -> date:
    """Primeiro dia (local) do dia, da semana (segunda-feira) ou do mês do momento."""
    local = as_utc(moment).astimezone(tz).date()
    if granularity == Granularity.WEEK:
        return local - timedelta(days=local.weekday())
    if granularity == Granularity.MONTH:
        return local.replace(day=1)
    return local


def _next_bucket(bucket: date, granularity: Granularity) -> date:
    if granularity == Granularity.DAY:
        return bucket + timedelta(days=1)
    if granularity == Granularity.WEEK:
        return bucket + timedelta(days=7)
    return date(bucket.year + bucket.month // 12, bucket.month % 12 + 1, 1)


def buckets_for(window: Window, granularity: Granularity, tz: tzinfo) -> list[date]:
    """Todos os intervalos da janela, inclusive os vazios (a série não tem buracos)."""
    first = bucket_of(window.start, granularity, tz)
    last = bucket_of(window.end - timedelta(microseconds=1), granularity, tz)
    buckets = [first]
    while buckets[-1] < last:
        buckets.append(_next_bucket(buckets[-1], granularity))
    return buckets


def approval_rate(approved: int, rejected: int) -> float | None:
    """Aprovadas sobre decididas (aprovadas + reprovadas); cancelamentos não entram."""
    decided = approved + rejected
    return round(approved / decided, 4) if decided else None


@dataclass(frozen=True)
class ProcessingTime:
    """Do recebimento à decisão do revisor (aprovação ou reprovação)."""

    average_hours: float | None
    median_hours: float | None
    samples: int


def processing_time(durations: list[timedelta]) -> ProcessingTime:
    if not durations:
        return ProcessingTime(None, None, 0)
    hours = [duration.total_seconds() / 3600 for duration in durations]
    return ProcessingTime(round(mean(hours), 1), round(median(hours), 1), len(hours))
