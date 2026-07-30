"""strutture: la revoca della conferma di lettura diventa una transizione

Revision ID: 0013
Revises: 0012
Create Date: 2026-07-30

`regime_lettura` porta l'evidenza datata che l'Host è stato informato della
soglia fiscale (`conteggio_confermato`, `confermato_il`). Il rientro sotto
soglia la cancellava con una `DELETE`: la prova che l'Host sia mai stato
informato sparisce, su una materia in cui la prova è il punto — e sarebbe una
cancellazione distruttiva fuori dalla lista esaustiva di AD-20. Da qui la riga
RESTA e la revoca si registra, nella forma di AD-19 (decisione MYL-68).

**`revocata_il`** — NULL significa «la conferma vale ORA». Non è un booleano:
la data è metà di ciò che rende la storia leggibile («informato il giorno X,
conferma revocata il giorno Y»). Le righe già presenti restano a NULL, ed è
corretto: nessuna di esse è stata revocata.

**Dall'unicità di `host_id` all'unicità della conferma VALIDA.** Con più giri
di soglia in tabella `uq_regime_lettura_host_id` vieterebbe la storia, quindi
si sostituisce con un indice unico PARZIALE sulle righe non revocate: è
l'invariante che serve davvero al codice («al più una conferma valida per
Host», che è ciò che rende legittimo il suo `one_or_none()`), e le righe
esistenti lo soddisfano già — sono tutte valide, ed erano una per Host.

Torna anche `ix_regime_lettura_host_id`, che la migrazione 0009 aveva tolto
perché duplicava l'indice del vincolo unico: quell'argomento cade adesso che il
vincolo copre le sole righe non revocate, mentre la storia di un Host si legge
su tutte.

Nessuna modifica distruttiva: si aggiunge una colonna e si scambiano due
indici, nessuna riga viene cancellata (AD-20, AR-11).
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "regime_lettura",
        sa.Column("revocata_il", sa.DateTime(timezone=True), nullable=True),
    )
    op.drop_constraint("uq_regime_lettura_host_id", "regime_lettura", type_="unique")
    op.create_index(
        "uq_regime_lettura_conferma_attiva",
        "regime_lettura",
        ["host_id"],
        unique=True,
        postgresql_where=sa.text("revocata_il IS NULL"),
    )
    op.create_index(op.f("ix_regime_lettura_host_id"), "regime_lettura", ["host_id"])


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
