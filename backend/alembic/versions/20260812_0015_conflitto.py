"""calendario: la tabella `conflitto` (Story 2.5, AD-5)

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-12

Additiva: un tipo, una tabella, un indice. Nessuna riga esistente viene
toccata (AD-20, AR-11).

**L'indice UNIQUE è PARZIALE, ed è il cuore della Story.** «Mai due Conflitti
aperti per la stessa coppia» (AD-5) non può essere imposto dal codice: due
Feed della stessa Struttura che concludono l'import insieme sono il caso
normale, e sotto concorrenza un controllo applicativo passa due volte. Il
vincolo sta qui, sulle tre colonne dell'identità e sul solo stato `rilevato`
— un Conflitto `decaduto` è storia, e vincolarlo per sempre renderebbe
invisibile un secondo Conflitto sulla stessa coppia invece che impossibile.

**Il CHECK sulla canonicalizzazione non è ridondante rispetto all'indice: è
ciò che lo rende efficace.** Con le due colonne libere di essere scambiate,
`(A,B)` e `(B,A)` sarebbero righe diverse per l'indice, e il vincolo
esisterebbe senza mordere — cioè la forma di difetto descritta in §4.2-4.

Il tipo `stato_conflitto` si può NOMINARE in questa stessa migrazione (il
CHECK lo fa): la restrizione di Postgres riguarda i valori aggiunti a un tipo
ESISTENTE con `ALTER TYPE … ADD VALUE`, non un tipo creato qui — è la
differenza con la migrazione 0014, dove `'manuale'` non era utilizzabile.
"""

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

STATO_CONFLITTO = sa.Enum(
    "rilevato",
    "gestito",
    "decaduto",
    name="stato_conflitto",
)


def upgrade() -> None:
    op.create_table(
        "conflitto",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("struttura_id", sa.Uuid(), nullable=False),
        sa.Column("prenotazione_min_id", sa.Uuid(), nullable=False),
        sa.Column("prenotazione_max_id", sa.Uuid(), nullable=False),
        sa.Column("stato", STATO_CONFLITTO, nullable=False),
        sa.Column("rilevato_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decaduto_il", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["host.id"]),
        sa.ForeignKeyConstraint(["struttura_id"], ["struttura.id"]),
        sa.ForeignKeyConstraint(["prenotazione_min_id"], ["prenotazione.id"]),
        sa.ForeignKeyConstraint(["prenotazione_max_id"], ["prenotazione.id"]),
        sa.CheckConstraint(
            "prenotazione_min_id < prenotazione_max_id",
            name="ck_conflitto_coppia_canonica",
        ),
        sa.CheckConstraint(
            "(stato = 'decaduto') = (decaduto_il IS NOT NULL)",
            name="ck_conflitto_decaduto_ha_istante",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_conflitto_host_id", "conflitto", ["host_id"])
    op.create_index("ix_conflitto_struttura_id", "conflitto", ["struttura_id"])
    op.create_index(
        "ix_conflitto_prenotazione_min_id", "conflitto", ["prenotazione_min_id"]
    )
    op.create_index(
        "ix_conflitto_prenotazione_max_id", "conflitto", ["prenotazione_max_id"]
    )
    op.create_index(
        "uq_conflitto_rilevato_per_coppia",
        "conflitto",
        ["struttura_id", "prenotazione_min_id", "prenotazione_max_id"],
        unique=True,
        postgresql_where=sa.text("stato = 'rilevato'"),
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
