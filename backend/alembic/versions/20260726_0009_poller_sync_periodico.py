"""calendario: validatori di cache e traccia del 304 (Story 2.2)

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-26

Tre modifiche, due scopi.

**Poller periodico (Story 2.2).** `feed_ical.etag` e `feed_ical.last_modified`
conservano i validatori di cache dell'ultimo import RIUSCITO, per mandarli
come `If-None-Match` / `If-Modified-Since` al giro successivo (AD-4);
`sync_run.non_modificato` registra che il portale ha risposto `304`, cioè un
run riuscito in cui non si è riconciliato nulla. Senza quest'ultima colonna un
run da 304 sarebbe indistinguibile da un run che ha riletto tutto senza
trovare novità: tutti i contatori a zero in entrambi i casi.

**Deriva di `alembic check` (MYL-44).** Il cancello di CI che verifica lo
schema contro i modelli non si poteva accendere finché `alembic check` restava
rosso su voci preesistenti. Qui si chiude l'ultima che richiede il database:
`ix_regime_lettura_host_id` è un indice non unico su una colonna che porta già
`uq_regime_lettura_host_id`, quindi duplica l'indice del vincolo senza
aggiungere nulla. Le altre due voci — gli indici parziali `ix_job_due` e
`ix_outbox_pending` — erano deriva del MODELLO, non dello schema: esistevano
nel database e non erano dichiarati, e si chiudono dichiarandoli
(`app/core/jobs.py`, `app/core/outbox.py`) senza toccare il database.

`drop_index` non è una modifica distruttiva ai sensi di AD-20: non cancella
righe. Nessuna lettura regredisce, perché il vincolo di unicità mantiene un
proprio indice sulla stessa colonna.
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Text e non String(n): l'`ETag` è una stringa opaca del portale e
    # `Last-Modified` va rimandato verbatim. Un troncamento silenzioso
    # renderebbe il validatore inservibile senza dire perché — e il sintomo
    # sarebbe «il 304 non arriva mai», cioè nessun sintomo.
    op.add_column("feed_ical", sa.Column("etag", sa.Text(), nullable=True))
    op.add_column("feed_ical", sa.Column("last_modified", sa.Text(), nullable=True))

    # `server_default` sulle righe già presenti, poi rimosso: le colonne NOT
    # NULL nascono con un default per non fallire sulle righe esistenti, ma
    # il default NON resta nello schema — il valore lo decide
    # l'applicazione, e un default nel database sopravvivrebbe a un `INSERT`
    # che dimentica la colonna, nascondendo l'omissione.
    op.add_column(
        "sync_run",
        sa.Column(
            "non_modificato", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.alter_column("sync_run", "non_modificato", server_default=None)

    op.drop_index("ix_regime_lettura_host_id", table_name="regime_lettura")


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
