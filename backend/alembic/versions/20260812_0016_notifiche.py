"""notifiche: `notifica` e `notifica_consegna` (Story 2.6, AD-10, AD-13)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-12

Additiva: due tipi, due tabelle, i loro indici. Nessuna riga esistente viene
toccata (AD-20, AR-11).

**I due UNIQUE sono i due check-then-write della Story**, e stanno qui e non
nel codice perché sotto concorrenza il codice perde (gara A3-5):

- `uq_notifica_per_riferimento` risponde a «è già stata notificata?». Due
  consegne concorrenti di `conflitto.rilevato` — o un secondo sync che rileva
  lo stesso Conflitto — trovano la riga già aperta e non ne creano una
  seconda. È PIENO e non parziale, al contrario di quello di `conflitto`: lì
  la stessa coppia può tornare a sovrapporsi e un secondo Conflitto è
  legittimo, qui il riferimento È il Conflitto.
- `uq_notifica_consegna_per_canale` chiude la stessa domanda sul canale: un
  canale servito una volta sola per notifica, qualunque cosa faccia il
  ritentativo.

Il CHECK `(stato = 'inviata') = (inviata_il IS NOT NULL)` vale nei due sensi,
come quello di `conflitto.decaduto_il`: nessuno stato di successo senza il suo
istante, nessun istante senza lo stato.

`notifica.riferimento_id` è deliberatamente **senza FK**: una FK verso
`conflitto` legherebbe lo schema di `notifiche` a quello di `calendario`
(AD-1), e il riferimento dell'Epic 3 sarà un Adempimento.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

CANALE_CONSEGNA = sa.Enum("in_app", "email", name="canale_consegna")
STATO_CONSEGNA = sa.Enum("in_attesa", "inviata", name="stato_consegna")


def upgrade() -> None:
    op.create_table(
        "notifica",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("tipo", sa.String(length=200), nullable=False),
        sa.Column("riferimento_id", sa.Uuid(), nullable=False),
        sa.Column("creata_il", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["host.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifica_host_id", "notifica", ["host_id"])

    op.create_table(
        "notifica_consegna",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("notifica_id", sa.Uuid(), nullable=False),
        sa.Column("canale", CANALE_CONSEGNA, nullable=False),
        sa.Column("stato", STATO_CONSEGNA, nullable=False),
        sa.Column("oggetto", sa.String(length=300), nullable=True),
        sa.Column("corpo", sa.Text(), nullable=True),
        sa.Column("inviata_il", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creata_il", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["host.id"]),
        sa.ForeignKeyConstraint(["notifica_id"], ["notifica.id"]),
        sa.CheckConstraint(
            "(stato = 'inviata') = (inviata_il IS NOT NULL)",
            name="ck_notifica_consegna_inviata_ha_istante",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifica_consegna_host_id", "notifica_consegna", ["host_id"])
    op.create_index(
        "ix_notifica_consegna_notifica_id", "notifica_consegna", ["notifica_id"]
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
