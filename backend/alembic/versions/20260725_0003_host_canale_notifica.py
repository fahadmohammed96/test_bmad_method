"""identity: canale di notifica preferito dell'Host (Story 1.3, UX-DR15)

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-25

"""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    canale = sa.Enum("in_app", "email", name="canale_notifica")
    canale.create(op.get_bind())
    op.add_column(
        "host",
        sa.Column(
            "canale_notifica_preferito",
            canale,
            nullable=False,
            server_default="email",
        ),
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
