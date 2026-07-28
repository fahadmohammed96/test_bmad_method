"""core: indice parziale sui job attivi (MYL-51)

Revision ID: 0012
Revises: 0011
Create Date: 2026-07-27

La query di idempotenza dei bootstrap periodici — «esiste già un job di QUESTO
tipo in stato `pending` o `running`?» — non aveva alcun indice utilizzabile.
`ix_job_due` è parziale su `status = 'pending'` e il predicato è
`IN ('pending', 'running')`: il pianificatore non può dimostrare l'implicazione
e cade sul sequential scan dell'intera tabella `job`, che dalla Story 2.2
cresce senza limite. Il costo si paga per primo all'avvio del worker, che fa
una di queste query per ogni Feed.

Solo `job_type` nella chiave: un indice di espressione su `payload->>'feed_id'`
legherebbe lo schema del kernel alla forma del payload di un dominio (AD-1), e
non serve — la clausola parziale riduce già i candidati ai job ATTIVI di quel
tipo, che sono al più uno per Feed.

`create_index` non è una modifica distruttiva (AD-20): non tocca alcuna riga.
"""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_job_attivi",
        "job",
        ["job_type"],
        unique=False,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    raise RuntimeError("Migrazioni forward-only (AR-11): downgrade vietato")
