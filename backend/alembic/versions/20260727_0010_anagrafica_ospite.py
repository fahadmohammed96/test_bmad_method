"""calendario: anagrafica `ospite` e decorrenza della sua retention (Story 2.3)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-27

Due modifiche, un solo invariante: AD-21.

**`ospite`** — anagrafica dell'Ospite, tenant-owned (`host_id` NOT NULL con FK
verso `host`, AD-2: non è un dato di riferimento e non entra in nessuna
allowlist). I tre campi personali sono TUTTI nullable, perché si scrive solo
ciò che il Feed fornisce esplicitamente o che l'Host inserisce volontariamente
— mai un valore dedotto (NFR-11). Nessun campo di documento d'identità: quelli
vivono solo in `ospite_documento` (Epic 3, AD-11).

`anonimizzato_il` è l'evidenza dell'azzeramento di retention. Senza, una riga
con i campi a NULL perché scaduta e una che non ha mai avuto contatti sono
indistinguibili — e la prima è un adempimento eseguito, che va potuto
dimostrare (NFR-15).

L'indice UNIQUE **parziale** su `prenotazione_id WHERE principale` impone dal
database «al più un Ospite principale per Prenotazione»: con due righe marcate
la griglia sceglierebbe a caso quale nome mostrare, e la scelta cambierebbe fra
due letture identiche.

**`prenotazione.cessata_il`** — istante in cui la Prenotazione è uscita da
`attiva` (AD-19), NULL finché è attiva. Non è `aggiornata_il`, che avanza a
ogni sync: qui serve una data che non si muove più, perché AD-21 fa decorrere
la retention dell'anagrafica dal `check_out` **o dall'uscita da `attiva` se
precedente**. Senza questa colonna la metà «se precedente» dell'invariante
resterebbe scritta e non applicata, e i contatti di una Prenotazione
cancellata sei mesi prima dell'arrivo resterebbero fino a sei mesi più il
periodo di retention.

Le righe già presenti restano a NULL, ed è corretto: `cessata_il` è una data
che nessuno ha registrato, e inventarla ora — mettendoci `aggiornata_il`, per
esempio — farebbe decorrere una retention da un istante che non è quello in
cui la Prenotazione è cessata. Per quelle righe decide il `check_out`, che è
un dato vero.

Nessuna modifica distruttiva: si aggiunge, non si cancella (AD-20, AR-11).
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ospite",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("prenotazione_id", sa.Uuid(), nullable=False),
        sa.Column("principale", sa.Boolean(), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("telefono", sa.String(length=50), nullable=True),
        sa.Column("creato_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggiornato_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anonimizzato_il", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["host_id"], ["host.id"]),
        # Nessun `ondelete`: la FK verso una tabella append-preserving non
        # deve poter propagare una cancellazione, e la guardia GS-6 lo
        # verifica sul modello (AD-4, AD-20).
        sa.ForeignKeyConstraint(["prenotazione_id"], ["prenotazione.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ospite_host_id", "ospite", ["host_id"])
    op.create_index("ix_ospite_prenotazione_id", "ospite", ["prenotazione_id"])
    op.create_index(
        "uq_ospite_principale_per_prenotazione",
        "ospite",
        ["prenotazione_id"],
        unique=True,
        postgresql_where=sa.text("principale"),
    )

    op.add_column(
        "prenotazione",
        sa.Column("cessata_il", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
