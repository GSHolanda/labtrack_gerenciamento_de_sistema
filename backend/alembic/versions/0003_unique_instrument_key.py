"""chave de instrumento única

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

A integração localiza o equipamento pelo hash da chave (`X-Instrument-Key`).
A constraint garante que um hash identifique no máximo um instrumento e cria o
índice usado nessa consulta.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_instruments_api_key_hash"), "instruments", ["api_key_hash"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_instruments_api_key_hash"), "instruments", type_="unique")
