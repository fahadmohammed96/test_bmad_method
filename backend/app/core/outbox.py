"""Transactional outbox (AD-1).

Ogni evento di dominio è scritto nella tabella `outbox` NELLA STESSA
TRANSAZIONE della modifica di stato che lo genera; il worker lo consegna
dopo il commit ai subscriber registrati. Il claim usa FOR UPDATE SKIP LOCKED
per non consegnare due volte con più worker.
"""

import logging
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7
from app.core.events import Catalog
from app.core.events import catalog as production_catalog

logger = logging.getLogger(__name__)

EventHandler = Callable[[Session, str, dict], None]


class OutboxEvent(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def emit(
    session: Session,
    event_name: str,
    payload: Mapping[str, object],
    *,
    catalog: Catalog | None = None,
) -> OutboxEvent:
    """Accoda un evento di dominio nella transazione corrente."""
    active_catalog = catalog if catalog is not None else production_catalog
    active_catalog.validate_event_payload(event_name, payload)
    event = OutboxEvent(event_name=event_name, payload=dict(payload))
    session.add(event)
    return event


class EventSubscribers:
    """Registro dei consumer in-process degli eventi di dominio."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def handlers_for(self, event_name: str) -> tuple[EventHandler, ...]:
        return tuple(self._handlers.get(event_name, ()))


# Registro di produzione: i moduli si sottoscrivono qui all'avvio del worker.
subscribers = EventSubscribers()


def deliver_pending(
    session: Session,
    event_subscribers: EventSubscribers | None = None,
    *,
    limit: int = 100,
) -> int:
    """Consegna gli eventi non ancora consegnati; ritorna quanti ne ha consegnati.

    Un handler che fallisce lascia l'evento non consegnato (riprovato al tick
    successivo, at-least-once): gli handler devono essere idempotenti.
    """
    subs = event_subscribers if event_subscribers is not None else subscribers
    pending = session.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.delivered_at.is_(None))
        .order_by(OutboxEvent.occurred_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()

    delivered = 0
    for event in pending:
        event.attempts += 1
        try:
            for handler in subs.handlers_for(event.event_name):
                handler(session, event.event_name, event.payload)
        except Exception:
            logger.exception(
                "consegna evento outbox fallita",
                extra={"event_name": event.event_name, "outbox_id": str(event.id)},
            )
            continue
        event.delivered_at = utcnow()
        delivered += 1
    session.flush()
    return delivered
