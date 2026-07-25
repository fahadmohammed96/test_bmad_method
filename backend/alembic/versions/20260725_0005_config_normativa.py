"""config_normativa: anagrafica ISTAT, config a validità temporale, audit

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-25

Le 20 Regioni sono anagrafica stabile e si seedano qui; i Comuni si
importano dal file ufficiale ISTAT (app.config_normativa.importa_comuni).
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op
from app.config_normativa.seed import REGIONI_ISTAT

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    regione = op.create_table(
        "regione",
        sa.Column("codice_istat", sa.String(length=2), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("codice_istat", name=op.f("pk_regione")),
    )
    op.bulk_insert(
        regione,
        [{"codice_istat": codice, "nome": nome} for codice, nome in REGIONI_ISTAT],
    )

    op.create_table(
        "comune",
        sa.Column("codice_istat", sa.String(length=6), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("provincia", sa.String(length=4), nullable=False),
        sa.Column("regione_codice_istat", sa.String(length=2), nullable=False),
        sa.PrimaryKeyConstraint("codice_istat", name=op.f("pk_comune")),
        sa.ForeignKeyConstraint(
            ["regione_codice_istat"],
            ["regione.codice_istat"],
            name=op.f("fk_comune_regione_codice_istat_regione"),
        ),
    )
    op.create_index(op.f("ix_comune_nome"), "comune", ["nome"])
    op.create_index(
        op.f("ix_comune_regione_codice_istat"), "comune", ["regione_codice_istat"]
    )

    periodicita = sa.Enum(
        "mensile", "trimestrale", "semestrale", "annuale", name="periodicita"
    )
    op.create_table(
        "comune_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("comune_codice_istat", sa.String(length=6), nullable=False),
        sa.Column("tassa_importo_cent", sa.Integer(), nullable=False),
        sa.Column("tassa_periodicita", periodicita, nullable=False),
        sa.Column("esenzione_eta_max", sa.Integer(), nullable=True),
        sa.Column("esenzione_notti_oltre", sa.Integer(), nullable=True),
        sa.Column("valido_dal", sa.Date(), nullable=False),
        sa.Column("valido_al", sa.Date(), nullable=True),
        sa.Column("creato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comune_config")),
        sa.ForeignKeyConstraint(
            ["comune_codice_istat"],
            ["comune.codice_istat"],
            name=op.f("fk_comune_config_comune_codice_istat_comune"),
        ),
    )
    op.create_index(
        op.f("ix_comune_config_comune_codice_istat"),
        "comune_config",
        ["comune_codice_istat"],
    )

    op.create_table(
        "regione_config",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("regione_codice_istat", sa.String(length=2), nullable=False),
        sa.Column("istat_tracciato", sa.String(length=80), nullable=False),
        sa.Column(
            "istat_periodicita",
            sa.Enum(name="periodicita", create_type=False),
            nullable=False,
        ),
        sa.Column("valido_dal", sa.Date(), nullable=False),
        sa.Column("valido_al", sa.Date(), nullable=True),
        sa.Column("creato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_regione_config")),
        sa.ForeignKeyConstraint(
            ["regione_codice_istat"],
            ["regione.codice_istat"],
            name=op.f("fk_regione_config_regione_codice_istat_regione"),
        ),
    )
    op.create_index(
        op.f("ix_regione_config_regione_codice_istat"),
        "regione_config",
        ["regione_codice_istat"],
    )

    op.create_table(
        "config_audit",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("attore", sa.String(length=200), nullable=False),
        sa.Column("entita", sa.String(length=40), nullable=False),
        sa.Column("entita_riferimento", sa.String(length=20), nullable=False),
        sa.Column("dati", JSONB(), nullable=False),
        sa.Column("creato_il", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_config_audit")),
    )

    op.add_column(
        "struttura",
        sa.Column("comune_codice_istat", sa.String(length=6), nullable=True),
    )
    op.add_column(
        "struttura",
        sa.Column("regione_codice_istat", sa.String(length=2), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_struttura_comune_codice_istat_comune"),
        "struttura",
        "comune",
        ["comune_codice_istat"],
        ["codice_istat"],
    )
    op.create_foreign_key(
        op.f("fk_struttura_regione_codice_istat_regione"),
        "struttura",
        "regione",
        ["regione_codice_istat"],
        ["codice_istat"],
    )
    op.create_index(
        op.f("ix_struttura_comune_codice_istat"),
        "struttura",
        ["comune_codice_istat"],
    )
    op.create_index(
        op.f("ix_struttura_regione_codice_istat"),
        "struttura",
        ["regione_codice_istat"],
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
