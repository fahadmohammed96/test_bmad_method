"""identity: tabelle host e sessione (AD-15, AD-18)

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-24

"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "host",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_host")),
        sa.UniqueConstraint("email", name=op.f("uq_host_email")),
    )
    op.create_table(
        "sessione",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessione")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_sessione_host_id_host")
        ),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessione_token_hash")),
    )
    op.create_index(op.f("ix_sessione_host_id"), "sessione", ["host_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
