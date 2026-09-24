"""Geração de leituras em torno da especificação do teste."""

import random
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal


def generate_value(
    spec_min: Decimal | None,
    spec_max: Decimal | None,
    decimal_places: int,
    *,
    oos: bool,
    rng: random.Random,
) -> Decimal:
    """Leitura dentro da faixa central da especificação ou, se ``oos``, fora dela.

    O valor já sai com as casas decimais do teste. Uma leitura OOS fica além de um
    dos limites existentes (os dois, se houver, são sorteados).
    """
    if spec_min is None and spec_max is None:
        raise ValueError("O teste precisa de ao menos um limite de especificação.")
    step = Decimal(1).scaleb(-decimal_places)
    low, high = _working_range(spec_min, spec_max)
    width = high - low or abs(low) * 0.1 or 1.0

    if not oos:
        if spec_min is not None and spec_min == spec_max:
            return spec_min.quantize(step, ROUND_HALF_UP)
        value = _quantize(rng.uniform(low + width * 0.2, high - width * 0.2), step)
        return _clamp(value, spec_min, spec_max, step)

    sides = [side for side, limit in (("low", spec_min), ("high", spec_max)) if limit is not None]
    offset = width * rng.uniform(0.05, 0.2)
    if rng.choice(sides) == "high":
        assert spec_max is not None
        beyond = (spec_max + step).quantize(step, ROUND_CEILING)
        return max(_quantize(float(spec_max) + offset, step), beyond)
    assert spec_min is not None
    beyond = (spec_min - step).quantize(step, ROUND_FLOOR)
    return min(_quantize(float(spec_min) - offset, step), beyond)


def is_in_spec(value: Decimal, spec_min: Decimal | None, spec_max: Decimal | None) -> bool:
    """Mesma regra do LabTrack: limites inclusivos; limite ausente não restringe."""
    return (spec_min is None or value >= spec_min) and (spec_max is None or value <= spec_max)


def _working_range(spec_min: Decimal | None, spec_max: Decimal | None) -> tuple[float, float]:
    """Faixa de trabalho; especificação unilateral ganha um lado plausível."""
    if spec_min is not None and spec_max is not None:
        return float(spec_min), float(spec_max)
    if spec_max is not None:
        high = float(spec_max)
        return high - (abs(high) * 0.8 or 1.0), high
    assert spec_min is not None
    low = float(spec_min)
    return low, low + (abs(low) * 0.5 or 1.0)


def _quantize(number: float, step: Decimal) -> Decimal:
    return Decimal(repr(number)).quantize(step, ROUND_HALF_UP)


def _clamp(
    value: Decimal, spec_min: Decimal | None, spec_max: Decimal | None, step: Decimal
) -> Decimal:
    # Arredonda para dentro da faixa quando o limite tem mais casas que o teste.
    if spec_min is not None and value < spec_min:
        return spec_min.quantize(step, ROUND_CEILING)
    if spec_max is not None and value > spec_max:
        return spec_max.quantize(step, ROUND_FLOOR)
    return value
