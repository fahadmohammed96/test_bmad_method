"""calendario: Canale `manuale` e coerenza di `(feed_id, ical_uid)` (MYL-61)

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-30

Due modifiche, entrambe **additive**: nessuna riga viene toccata, nessuna
colonna rimossa (AD-20, AR-11).

**1. Il valore `manuale` del tipo `canale_feed`.** Il Glossario (PRD §4)
definisce il Canale come «la fonte OTA di una Prenotazione: Airbnb,
Booking.com, o inserimento manuale»: il valore mancava perché fino alla Story
2.4 nessun percorso scriveva Prenotazioni che non venissero da un Feed.

`ALTER TYPE … ADD VALUE` e non un tipo nuovo con `USING`: quello sarebbe una
riscrittura di tabella su dati append-only, per aggiungere un valore. Il nuovo
valore **non si usa in questa migrazione** — né in un DEFAULT, né in un CHECK,
né in una UPDATE — e la ragione è precisa: Postgres ammette `ADD VALUE` dentro
una transazione ma vieta di *usare* il valore prima del commit, e `env.py`
esegue l'intero `upgrade` in **una sola** transazione. Una migrazione futura
che debba nominare `'manuale'` non può quindi farlo qui accanto: le serve un
`upgrade` separato, eseguito dopo il commit di questo.

**2. Il CHECK `(feed_id IS NULL) = (ical_uid IS NULL)`.** Rende
irrappresentabile la forma MISTA — un `feed_id` senza `ical_uid` — che
sfuggirebbe al UNIQUE `(feed_id, ical_uid)`, perché in Postgres i `NULL` sono
distinti fra loro dentro un indice: lo stesso Feed potrebbe produrre righe
duplicate e l'upsert idempotente non se ne accorgerebbe. Le righe esistenti lo
soddisfano tutte per costruzione (l'unico scrittore era l'import, che scrive
sempre entrambi i campi), quindi la validazione al momento della creazione del
vincolo non può fallire su dati reali.

Il CHECK non nomina il Canale: la biconditional fra «senza Feed» e «Canale
manuale» sarebbe pure vera, ma esprimerla qui richiederebbe il letterale
`'manuale'`, cioè l'uso vietato del punto 1.
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # `IF NOT EXISTS`: la migrazione resta rieseguibile su un database in cui
    # il valore fosse già stato aggiunto a mano, senza abortire la
    # transazione dell'intero `upgrade`.
    op.execute("ALTER TYPE canale_feed ADD VALUE IF NOT EXISTS 'manuale'")
    op.create_check_constraint(
        "ck_prenotazione_feed_e_uid_insieme",
        "prenotazione",
        "(feed_id IS NULL) = (ical_uid IS NULL)",
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
