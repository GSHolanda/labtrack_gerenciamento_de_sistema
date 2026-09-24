"""dados de referência: os quatro perfis do sistema

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24

Os perfis são dados de referência (o código depende deles), por isso são
criados pela migração e não por um seed opcional. Os valores ficam copiados
aqui de propósito: uma migração deve continuar reproduzível mesmo que o
código da aplicação mude.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLES = [
    ("ADMIN", "Administrador", "Gerencia usuários, cadastros, testes e instrumentos."),
    ("ANALYST", "Analista de Laboratório", "Registra amostras, executa análises e insere resultados."),
    ("REVIEWER", "Revisor", "Revisa resultados e aprova ou reprova amostras."),
    ("MANAGER", "Gestor", "Acompanha indicadores, audit trail e pode cancelar amostras."),
]

roles = sa.table(
    "roles",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.Text),
)


def upgrade() -> None:
    op.bulk_insert(roles, [{"code": c, "name": n, "description": d} for c, n, d in ROLES])


def downgrade() -> None:
    op.execute(roles.delete().where(roles.c.code.in_([code for code, _, _ in ROLES])))
