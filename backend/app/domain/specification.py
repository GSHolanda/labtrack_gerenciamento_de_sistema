"""Especificação de testes: resolução dos limites vigentes."""

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import SpecStatus


@dataclass(frozen=True)
class SpecLimits:
    spec_min: Decimal | None
    spec_max: Decimal | None


def resolve_limits(default: SpecLimits, product_override: SpecLimits | None = None) -> SpecLimits:
    """RN-06: o limite definido para o produto prevalece sobre o padrão do teste.

    Cada lado é resolvido separadamente: um produto pode sobrescrever só o máximo.
    """
    if product_override is None:
        return default
    return SpecLimits(
        spec_min=product_override.spec_min
        if product_override.spec_min is not None
        else default.spec_min,
        spec_max=product_override.spec_max
        if product_override.spec_max is not None
        else default.spec_max,
    )


def validate_limits(spec_min: Decimal | None, spec_max: Decimal | None) -> str | None:
    """Retorna a mensagem de erro, ou ``None`` se os limites forem coerentes."""
    if spec_min is not None and spec_max is not None and spec_min > spec_max:
        return "O limite mínimo não pode ser maior que o máximo."
    return None


def evaluate(value: Decimal, spec_min: Decimal | None, spec_max: Decimal | None) -> SpecStatus:
    """RN-16: dentro da especificação se ``spec_min <= valor <= spec_max``.

    Limites são inclusivos; um limite ausente não restringe aquele lado. A
    comparação usa ``Decimal``, então 7.5 <= 7.5 é exato.
    """
    if spec_min is not None and value < spec_min:
        return SpecStatus.OOS
    if spec_max is not None and value > spec_max:
        return SpecStatus.OOS
    return SpecStatus.IN_SPEC
