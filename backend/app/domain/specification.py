"""Especificação de testes: resolução dos limites vigentes."""

from dataclasses import dataclass
from decimal import Decimal


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
