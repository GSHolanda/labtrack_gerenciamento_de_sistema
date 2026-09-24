import random
from decimal import Decimal

import pytest

from simulator.measurement import generate_value, is_in_spec

D = Decimal
SPECS = [
    (D("5.5"), D("7.0"), 2),  # bilateral
    (None, D("0.5"), 2),  # só máximo (umidade)
    (None, D(100), 0),  # só máximo, inteiro (contagem microbiana)
    (D("95.0"), None, 1),  # só mínimo
    (D("-2.0"), D("2.0"), 1),  # faixa que cruza o zero
    (D(0), None, 2),  # mínimo zero
    (D("7.005"), D("7.095"), 2),  # limites com mais casas que o teste
]


@pytest.mark.parametrize(("spec_min", "spec_max", "places"), SPECS)
def test_in_spec_values_respect_limits_and_places(
    spec_min: Decimal | None, spec_max: Decimal | None, places: int
) -> None:
    rng = random.Random(7)
    for _ in range(300):
        value = generate_value(spec_min, spec_max, places, oos=False, rng=rng)
        assert is_in_spec(value, spec_min, spec_max), value
        assert -value.as_tuple().exponent == places


@pytest.mark.parametrize(("spec_min", "spec_max", "places"), SPECS)
def test_oos_values_fall_outside_the_specification(
    spec_min: Decimal | None, spec_max: Decimal | None, places: int
) -> None:
    rng = random.Random(11)
    values = [generate_value(spec_min, spec_max, places, oos=True, rng=rng) for _ in range(300)]
    assert not any(is_in_spec(value, spec_min, spec_max) for value in values)
    if spec_min is not None and spec_max is not None:  # os dois lados são sorteados
        assert any(value > spec_max for value in values)
        assert any(value < spec_min for value in values)


def test_equal_limits_produce_the_exact_value() -> None:
    value = generate_value(D("1.00"), D("1.00"), 2, oos=False, rng=random.Random(1))
    assert value == D("1.00")


def test_specification_without_limits_is_refused() -> None:
    with pytest.raises(ValueError, match="limite"):
        generate_value(None, None, 2, oos=False, rng=random.Random(1))


def test_same_seed_repeats_the_readings() -> None:
    def readings(seed: int) -> list[Decimal]:
        rng = random.Random(seed)
        return [generate_value(D("5.5"), D("7.0"), 2, oos=False, rng=rng) for _ in range(5)]

    assert readings(3) == readings(3)
    assert readings(3) != readings(4)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(D("5.5"), True), (D("7.0"), True), (D("5.4999"), False), (D("7.0001"), False)],
)
def test_limits_are_inclusive(value: Decimal, expected: bool) -> None:
    assert is_in_spec(value, D("5.5"), D("7.0")) is expected
