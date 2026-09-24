"""Modelos ORM (SQLAlchemy) que mapeiam as tabelas do banco relacional.

Descrevem estrutura e constraints; não contêm regra de negócio nem conhecem a
camada HTTP.

Pode importar: ``database``, ``domain``, ``core``.
"""

from app.models.audit import AuditLog
from app.models.integration import InstrumentResult
from app.models.master_data import Client, Instrument, Product, ProductSpecification, TestDefinition
from app.models.sample import Sample, SampleStatusHistory, SampleTest, TestResult
from app.models.security import Role, User

__all__ = [
    "AuditLog",
    "Client",
    "Instrument",
    "InstrumentResult",
    "Product",
    "ProductSpecification",
    "Role",
    "Sample",
    "SampleStatusHistory",
    "SampleTest",
    "TestDefinition",
    "TestResult",
    "User",
]
