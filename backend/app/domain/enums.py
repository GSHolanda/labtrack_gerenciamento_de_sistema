"""Enumerações do domínio LIMS.

São a fonte única dos valores válidos: os modelos geram as constraints
``CHECK`` do banco a partir delas e os schemas da API as usam na validação.
"""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    REVIEWER = "REVIEWER"
    MANAGER = "MANAGER"


class SampleStatus(StrEnum):
    RECEIVED = "RECEIVED"
    IN_ANALYSIS = "IN_ANALYSIS"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


FINAL_SAMPLE_STATUSES = frozenset(
    {SampleStatus.APPROVED, SampleStatus.REJECTED, SampleStatus.CANCELLED}
)


class SamplePriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class SampleOrigin(StrEnum):
    PRODUCTION = "PRODUCTION"
    RAW_MATERIAL = "RAW_MATERIAL"
    STABILITY = "STABILITY"
    CUSTOMER = "CUSTOMER"
    ENVIRONMENTAL = "ENVIRONMENTAL"


class SampleTestStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class SpecStatus(StrEnum):
    IN_SPEC = "IN_SPEC"
    OOS = "OOS"


class ResultSource(StrEnum):
    MANUAL = "MANUAL"
    INSTRUMENT = "INSTRUMENT"


class InstrumentType(StrEnum):
    PH_METER = "PH_METER"
    HPLC = "HPLC"
    BALANCE = "BALANCE"
    DENSITY_METER = "DENSITY_METER"
    MOISTURE_ANALYZER = "MOISTURE_ANALYZER"
    VISCOMETER = "VISCOMETER"
    THERMOMETER = "THERMOMETER"
    CONDUCTIVITY_METER = "CONDUCTIVITY_METER"


class InstrumentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    INACTIVE = "INACTIVE"


class InstrumentMessageStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class ActorType(StrEnum):
    USER = "USER"
    INSTRUMENT = "INSTRUMENT"
    SYSTEM = "SYSTEM"
