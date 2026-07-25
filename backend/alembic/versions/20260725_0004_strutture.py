"""strutture: tabella struttura con stato attiva/archiviata (FR-1, AD-20)

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-25

"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_table crea da sé il tipo enum: niente .create() esplicito.
    stato = sa.Enum("attiva", "archiviata", name="stato_struttura")
    op.create_table(
        "struttura",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("comune", sa.String(length=120), nullable=False),
        sa.Column("regione", sa.String(length=80), nullable=False),
        sa.Column("cin", sa.String(length=30), nullable=True),
        sa.Column("stato", stato, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_struttura")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_struttura_host_id_host")
        ),
    )
    op.create_index(op.f("ix_struttura_host_id"), "struttura", ["host_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
