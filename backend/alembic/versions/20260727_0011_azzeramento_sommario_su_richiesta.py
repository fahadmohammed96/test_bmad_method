"""calendario: evidenza dell'azzeramento del sommario e audit su richiesta

Revision ID: 0011
Revises: 0010
Create Date: 2026-07-27

Due aggiunte, un solo invariante: AD-21.

**`prenotazione.anonimizzato_il`** — evidenza dell'azzeramento del `sommario`,
sulla riga il cui campo è stato azzerato. Non è simmetria con
`ospite.anonimizzato_il`: è la colonna su cui l'upsert di AD-4 decide se ha
davanti una Prenotazione anonimizzata, e quindi se il `sommario` non va
riscritto. Senza, un feed che conserva i VEVENT passati ripopolerebbe il campo
appena azzerato e l'evidenza attesterebbe un azzeramento non più vero — cioè
la guardia di non-ripopolamento non sarebbe nemmeno scrivibile.

Le righe già presenti restano a NULL, ed è corretto: nessuna di esse è stata
azzerata, e marcarle direbbe il falso su un adempimento mai avvenuto. Il primo
giro del job di retention marcherà quelle che ne hanno bisogno.

**`azzeramento_audit`** — chi/cosa/quando degli azzeramenti CHIESTI (NFR-15).
Il job periodico non ci scrive: la sua evidenza è `anonimizzato_il` sulle
righe. Qui si registra ciò che quell'evidenza non può portare — che qualcuno
ha *chiesto* la cancellazione, e chi — con la stessa forma di `config_audit`
per gli endpoint `/interno` (AD-9). Tenant-owned (`host_id` NOT NULL con FK
verso `host`, AD-2): «tutti gli Ospiti di un Host» resta dentro quell'Host.
Nessun campo può contenere dati personali: `riferimento` è un identificatore e
i due conteggi sono numeri (AD-16, NFR-11).

Nessuna modifica distruttiva: si aggiunge, non si cancella (AD-20, AR-11).
"""

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prenotazione",
        sa.Column("anonimizzato_il", sa.DateTime(timezone=True), nullable=True),
    )

    # `create_table` con una colonna Enum crea da sé il tipo Postgres: una
    # `enum.create(bind)` esplicita qui darebbe DuplicateObject (idioma già
    # incontrato fra le migrazioni 0003 e 0004).
    op.create_table(
        "azzeramento_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("attore", sa.String(length=200), nullable=False),
        sa.Column(
            "ambito",
            sa.Enum("ospite", "host", name="ambito_azzeramento"),
            nullable=False,
        ),
        sa.Column("riferimento", sa.Uuid(), nullable=False),
        sa.Column("anagrafiche_azzerate", sa.Integer(), nullable=False),
        sa.Column("sommari_azzerati", sa.Integer(), nullable=False),
        sa.Column("eseguito_il", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["host_id"], ["host.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_azzeramento_audit_host_id", "azzeramento_audit", ["host_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
