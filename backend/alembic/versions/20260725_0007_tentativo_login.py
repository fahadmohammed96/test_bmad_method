"""identity: tracce dei tentativi di login per il freno agli abusi (G-5)

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-25

Tabella pre-autenticazione: nessun `host_id`, perché si scrive prima di
sapere se l'account esiste (legarla all'Host rivelerebbe quali email
sono registrate). Le righe vecchie le elimina il purge periodico.
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tentativo_login",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("origine", sa.String(length=60), nullable=False),
        sa.Column("avvenuto_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tentativo_login")),
    )
    op.create_index(op.f("ix_tentativo_login_email"), "tentativo_login", ["email"])
    op.create_index(op.f("ix_tentativo_login_origine"), "tentativo_login", ["origine"])
    op.create_index(
        op.f("ix_tentativo_login_avvenuto_il"), "tentativo_login", ["avvenuto_il"]
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
