"""Worker (AD-1, AD-10): processo dedicato dello stesso codebase.

Consegna gli eventi outbox dopo il commit ed esegue i job durevoli scaduti.
Avvio: `python -m app.core.worker`.
"""

import logging
import time
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.core import jobs as jobs_module
from app.core import outbox as outbox_module
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.jobs import JobHandlers, run_due_jobs
from app.core.outbox import EventSubscribers, deliver_pending

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerTick:
    eventi_consegnati: int
    job_eseguiti: int


def run_once(
    session_factory: sessionmaker,
    *,
    subscribers: EventSubscribers | None = None,
    handlers: JobHandlers | None = None,
) -> WorkerTick:
    """Un tick del worker: prima la consegna outbox, poi i job scaduti."""
    subs = subscribers if subscribers is not None else outbox_module.subscribers
    hnds = handlers if handlers is not None else jobs_module.handlers

    with session_factory() as session:
        eventi = deliver_pending(session, subs)
        session.commit()
    with session_factory() as session:
        eseguiti = run_due_jobs(session, hnds)
        session.commit()
    return WorkerTick(eventi_consegnati=eventi, job_eseguiti=eseguiti)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    factory = get_sessionmaker()
    logger.info("worker avviato", extra={"env": settings.env})
    while True:
        tick = run_once(factory)
        if tick.eventi_consegnati == 0 and tick.job_eseguiti == 0:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
