"""Contratos dos cadastros: clientes, produtos, tipos de teste e plano analítico."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

from app.domain.enums import InstrumentType
from app.domain.specification import validate_limits

Code = Annotated[
    str,
    # Normaliza antes de validar o formato: "cli-001" vira "CLI-001".
    BeforeValidator(lambda value: value.strip().upper() if isinstance(value, str) else value),
    StringConstraints(pattern=r"^[A-Z0-9_-]{2,30}$"),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Limit = Annotated[Decimal, Field(max_digits=14, decimal_places=4)]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Read(BaseModel):
    model_config = ConfigDict(from_attributes=True)


@dataclass(frozen=True)
class MasterDataFilter:
    q: str | None = None
    is_active: bool | None = None


# --- Clientes -----------------------------------------------------------------


class ClientCreate(_Input):
    code: Code = Field(examples=["CLI-001"])
    name: Name = Field(examples=["Farmacêutica Aurora"])
    tax_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    contact_email: EmailStr | None = None


class ClientUpdate(_Input):
    name: Name | None = None
    tax_id: Annotated[str, StringConstraints(strip_whitespace=True, max_length=20)] | None = None
    contact_email: EmailStr | None = None
    is_active: bool | None = None


class ClientRead(_Read):
    id: int
    code: str
    name: str
    tax_id: str | None
    contact_email: str | None
    is_active: bool
    created_at: datetime


# --- Produtos -----------------------------------------------------------------


class ProductCreate(_Input):
    code: Code = Field(examples=["PRD-001"])
    name: Name = Field(examples=["Xampu Neutro 500 mL"])
    category: ShortText | None = None
    description: str | None = None


class ProductUpdate(_Input):
    name: Name | None = None
    category: ShortText | None = None
    description: str | None = None
    is_active: bool | None = None


class ProductRead(_Read):
    id: int
    code: str
    name: str
    category: str | None
    description: str | None
    is_active: bool
    created_at: datetime


# --- Tipos de teste -----------------------------------------------------------


class _LimitsValidation(BaseModel):
    @model_validator(mode="after")
    def _check_limits(self) -> Self:
        error = validate_limits(getattr(self, "spec_min", None), getattr(self, "spec_max", None))
        if error:
            raise ValueError(error)
        return self


class TestDefinitionCreate(_Input, _LimitsValidation):
    __test__ = False

    code: Code = Field(examples=["PH"], description="Identificador usado também na integração")
    name: Name = Field(examples=["pH"])
    unit: ShortText = Field(examples=["pH"])
    spec_min: Limit | None = Field(default=None, examples=[6.5])
    spec_max: Limit | None = Field(default=None, examples=[7.5])
    method: Name = Field(examples=["Potenciometria"])
    instrument_type: InstrumentType | None = None
    decimal_places: int = Field(default=2, ge=0, le=6)
    description: str | None = None

    @model_validator(mode="after")
    def _require_a_limit(self) -> Self:
        if self.spec_min is None and self.spec_max is None:
            raise ValueError("Informe ao menos um limite de especificação.")
        return self


class TestDefinitionUpdate(_Input):
    """O código não pode ser alterado: é a chave usada pelos instrumentos."""

    __test__ = False

    name: Name | None = None
    unit: ShortText | None = None
    spec_min: Limit | None = None
    spec_max: Limit | None = None
    method: Name | None = None
    instrument_type: InstrumentType | None = None
    decimal_places: int | None = Field(default=None, ge=0, le=6)
    description: str | None = None
    is_active: bool | None = None


class TestDefinitionRead(_Read):
    __test__ = False

    id: int
    code: str
    name: str
    unit: str
    spec_min: Decimal | None
    spec_max: Decimal | None
    method: str
    instrument_type: InstrumentType | None
    decimal_places: int
    description: str | None
    is_active: bool


# --- Plano analítico do produto -----------------------------------------------


class SpecificationItem(_Input, _LimitsValidation):
    test_definition_id: int
    spec_min: Limit | None = Field(default=None, description="Sobrescreve o limite padrão")
    spec_max: Limit | None = Field(default=None, description="Sobrescreve o limite padrão")


class SpecificationRead(BaseModel):
    test_definition_id: int
    test_code: str
    test_name: str
    unit: str
    spec_min: Decimal | None = Field(description="Limite efetivo para o produto")
    spec_max: Decimal | None = Field(description="Limite efetivo para o produto")
    overrides_default: bool
    product_spec_min: Decimal | None = Field(
        default=None, description="Limite mínimo próprio do produto (vazio: vale o padrão)"
    )
    product_spec_max: Decimal | None = Field(
        default=None, description="Limite máximo próprio do produto (vazio: vale o padrão)"
    )
