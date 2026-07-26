"""calendario: feed_ical, sync_run, prenotazione (Story 2.1)

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-26

Tre tabelle tenant-owned (AD-2). Il vincolo che conta è
`uq_prenotazione_feed_ical_uid`: l'idempotenza dell'import è imposta dal
DATABASE, non da un pre-check applicativo — sotto concorrenza a decidere
deve essere il constraint (A3-1).

Nessuna FK verso queste tabelle dichiara `ondelete`: append-preserving è
un invariante di dato (AD-4, AD-19, AD-20) e una CASCADE lo aggirerebbe
senza che nessuno scriva un DELETE.
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# `create_table` crea da sé i tipi Postgres degli Enum che dichiara: il
# primo uso porta i valori, i successivi riusano il tipo già creato con
# `create_type=False` (idioma già in migrazione 0005).
CANALE_FEED = sa.Enum("airbnb", "booking", "altro", name="canale_feed")
CANALE_FEED_ESISTENTE = sa.Enum(name="canale_feed", create_type=False)
ESITO_SYNC_RUN = sa.Enum("riuscito", "fallito", name="esito_sync_run")
CATEGORIA_ERRORE_SYNC = sa.Enum(
    "url_non_raggiungibile",
    "timeout",
    "risposta_troppo_grande",
    "esito_http_inatteso",
    "feed_non_valido",
    "feed_senza_eventi",
    name="categoria_errore_sync",
)
STATO_PRENOTAZIONE = sa.Enum(
    "attiva", "cancellata", "rimossa_dal_feed", name="stato_prenotazione"
)


def upgrade() -> None:
    op.create_table(
        "feed_ical",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("struttura_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canale", CANALE_FEED, nullable=False),
        sa.Column("collegato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feed_ical")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_feed_ical_host_id_host")
        ),
        sa.ForeignKeyConstraint(
            ["struttura_id"],
            ["struttura.id"],
            name=op.f("fk_feed_ical_struttura_id_struttura"),
        ),
    )
    op.create_index(op.f("ix_feed_ical_host_id"), "feed_ical", ["host_id"])
    op.create_index(op.f("ix_feed_ical_struttura_id"), "feed_ical", ["struttura_id"])

    op.create_table(
        "sync_run",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("esito", ESITO_SYNC_RUN, nullable=False),
        sa.Column("categoria_errore", CATEGORIA_ERRORE_SYNC, nullable=True),
        sa.Column("prenotazioni_importate", sa.Integer(), nullable=False),
        sa.Column("prenotazioni_aggiornate", sa.Integer(), nullable=False),
        sa.Column("prenotazioni_rimosse_dal_feed", sa.Integer(), nullable=False),
        sa.Column("prenotazioni_ricomparse", sa.Integer(), nullable=False),
        sa.Column("eventi_malformati", sa.Integer(), nullable=False),
        sa.Column("eventi_ricorrenti_non_espansi", sa.Integer(), nullable=False),
        sa.Column("iniziato_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("concluso_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sync_run")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_sync_run_host_id_host")
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"], ["feed_ical.id"], name=op.f("fk_sync_run_feed_id_feed_ical")
        ),
    )
    op.create_index(op.f("ix_sync_run_host_id"), "sync_run", ["host_id"])
    op.create_index(op.f("ix_sync_run_feed_id"), "sync_run", ["feed_id"])

    op.create_table(
        "prenotazione",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("struttura_id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=True),
        sa.Column("ical_uid", sa.String(length=500), nullable=True),
        sa.Column("canale", CANALE_FEED_ESISTENTE, nullable=False),
        sa.Column("check_in", sa.Date(), nullable=False),
        sa.Column("check_out", sa.Date(), nullable=False),
        sa.Column("sommario", sa.String(length=500), nullable=True),
        sa.Column("stato", STATO_PRENOTAZIONE, nullable=False),
        sa.Column("creata_il", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aggiornata_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prenotazione")),
        sa.ForeignKeyConstraint(
            ["host_id"], ["host.id"], name=op.f("fk_prenotazione_host_id_host")
        ),
        sa.ForeignKeyConstraint(
            ["struttura_id"],
            ["struttura.id"],
            name=op.f("fk_prenotazione_struttura_id_struttura"),
        ),
        sa.ForeignKeyConstraint(
            ["feed_id"],
            ["feed_ical.id"],
            name=op.f("fk_prenotazione_feed_id_feed_ical"),
        ),
        sa.UniqueConstraint(
            "feed_id", "ical_uid", name="uq_prenotazione_feed_ical_uid"
        ),
    )
    op.create_index(op.f("ix_prenotazione_host_id"), "prenotazione", ["host_id"])
    op.create_index(
        op.f("ix_prenotazione_struttura_id"), "prenotazione", ["struttura_id"]
    )
    op.create_index(op.f("ix_prenotazione_feed_id"), "prenotazione", ["feed_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
