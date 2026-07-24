"""Test del worker (AD-1, AD-10): processo dedicato dello stesso codebase
che consegna gli eventi outbox dopo il commit ed esegue i job scaduti.
"""

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.date_range import utcnow
from app.core.events import Catalog
from app.core.jobs import JobHandlers, schedule
from app.core.outbox import EventSubscribers, emit
from app.core.worker import run_once


@pytest.fixture
def test_catalog() -> Catalog:
    c = Catalog()
    c.register_event("struttura.creata", payload_keys=("struttura_id", "host_id"))
    c.register_job("promemoria.invia", payload_keys=("adempimento_id",))
    return c


def test_un_tick_consegna_outbox_ed_esegue_job(
    pg_engine: Engine, db_session: Session, test_catalog: Catalog
) -> None:
    eventi: list[str] = []
    job_eseguiti: list[str] = []

    subscribers = EventSubscribers()
    subscribers.subscribe("struttura.creata", lambda s, n, p: eventi.append(n))
    handlers = JobHandlers()
    handlers.register("promemoria.invia")(
        lambda s, p: job_eseguiti.append(p["adempimento_id"])
    )

    emit(
        db_session,
        "struttura.creata",
        {"struttura_id": str(uuid.uuid4()), "host_id": str(uuid.uuid4())},
        catalog=test_catalog,
    )
    schedule(
        db_session,
        "promemoria.invia",
        {"adempimento_id": "adempimento-1"},
        due_at=utcnow() - timedelta(seconds=1),
        catalog=test_catalog,
    )
    db_session.commit()

    tick = run_once(sessionmaker(pg_engine), subscribers=subscribers, handlers=handlers)

    assert tick.eventi_consegnati == 1
    assert tick.job_eseguiti == 1
    assert eventi == ["struttura.creata"]
    assert job_eseguiti == ["adempimento-1"]
