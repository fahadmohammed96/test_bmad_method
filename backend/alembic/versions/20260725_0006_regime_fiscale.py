"""regime fiscale: parametri in configurazione e conferma di lettura

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-25

Il Regime resta DERIVATO (AD-12): qui non si persiste nessuno stato di
regime, solo i parametri normativi e la conferma di lettura del pannello.
"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parametro_fiscale",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("soglia_strutture", sa.Integer(), nullable=False),
        sa.Column("regime_sotto_soglia", sa.String(length=60), nullable=False),
        sa.Column("regime_da_soglia", sa.String(length=60), nullable=False),
        sa.Column("testo_sotto_soglia", sa.Text(), nullable=False),
        sa.Column("testo_da_soglia", sa.Text(), nullable=False),
        sa.Column("aliquote_citate", sa.String(length=200), nullable=False),
        sa.Column("valido_dal", sa.Date(), nullable=False),
        sa.Column("valido_al", sa.Date(), nullable=True),
        sa.Column("creato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_parametro_fiscale")),
    )

    op.create_table(
        "regime_lettura",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("conteggio_confermato", sa.Integer(), nullable=False),
        sa.Column("confermato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regime_lettura")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_regime_lettura_host_id_host")
        ),
        sa.UniqueConstraint("host_id", name=op.f("uq_regime_lettura_host_id")),
    )
    op.create_index(op.f("ix_regime_lettura_host_id"), "regime_lettura", ["host_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
