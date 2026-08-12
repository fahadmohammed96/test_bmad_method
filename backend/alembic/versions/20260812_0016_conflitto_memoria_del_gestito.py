"""calendario: `conflitto.gestito_il`, la memoria della decisione (F4, AD-5)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-12

Additiva: una colonna nullable e un CHECK. Nessuna riga esistente viene
toccata (AD-20, AR-11), e **non serve alcun backfill**: nessun percorso di
codice scrive oggi lo stato `gestito` (`tests/test_conflitti_niente_auto_chiusura.py`
lo impone), quindi non esiste una riga la cui decisione sia già andata persa.

È la ragione per cui questa migrazione arriva ADESSO e non con la Story 2.7:
oggi è una colonna vuota su righe che non hanno niente da ricordare; dopo la
2.7 sarebbe la stessa colonna più una ricostruzione di fatti che nessuna
tabella conserva più — cioè un dato che non si può recuperare, non una
migrazione più lunga.

**Il CHECK è un'IMPLICAZIONE e non un'equivalenza**, al contrario di
`ck_conflitto_decaduto_ha_istante` della 0015. `gestito` senza il suo istante
è una decisione senza il quando, e la finestra configurabile della 2.7 si
misura proprio da lì; ma `gestito_il` valorizzato su un Conflitto `decaduto` è
esattamente lo stato che questa colonna esiste per rendere rappresentabile.
Un `=` per simmetria vieterebbe il caso che si vuole ottenere.
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conflitto",
        sa.Column("gestito_il", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_conflitto_gestito_ha_istante",
        "conflitto",
        "stato <> 'gestito' OR gestito_il IS NOT NULL",
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
