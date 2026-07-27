"""Entrypoint applicativo del worker: `python -m app.worker`.

`app.core.worker` è il ciclo generico del kernel e non conosce i domini
(AD-1). Qui si importano i moduli che registrano handler e subscriber,
si assicura il bootstrap dei job periodici, e poi si cede il controllo
al ciclo.
"""

import logging

# Import con effetto di registrazione: ogni modulo dichiara qui i propri
# handler di job e i propri subscriber di eventi.
from app.calendario import jobs as calendario_jobs
from app.core.db import get_sessionmaker
from app.core.worker import main as ciclo_worker
from app.identity import jobs as identity_jobs  # noqa: F401

logger = logging.getLogger(__name__)


def bootstrap_job_periodici() -> None:
    """Rimette in coda i cicli periodici se mancano (idempotente).

    Una sola transazione per tutti: se il bootstrap del poller fallisce, il
    purge non deve restare accodato da solo dando l'impressione che l'avvio
    sia riuscito.
    """
    with get_sessionmaker()() as db:
        identity_jobs.assicura_purge_periodico(db)
        calendario_jobs.bootstrap_sync_periodico(db)
        calendario_jobs.assicura_retention_periodica(db)
        db.commit()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bootstrap_job_periodici()
    ciclo_worker()


if __name__ == "__main__":
    main()
