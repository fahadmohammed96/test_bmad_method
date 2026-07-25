"""Test della transactional outbox (AD-1).

L'evento è scritto nella stessa transazione della modifica di stato;
il worker lo consegna dopo il commit; il claim usa SKIP LOCKED.
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import Catalog, PayloadValidationError, UnknownTypeError
from app.core.outbox import EventSubscribers, OutboxEvent, deliver_pending, emit


@pytest.fixture
def test_catalog() -> Catalog:
    c = Catalog()
    c.register_event("struttura.creata", payload_keys=("struttura_id", "host_id"))
    return c


def _payload() -> dict[str, str]:
    return {"struttura_id": str(uuid.uuid4()), "host_id": str(uuid.uuid4())}


class TestEmit:
    def test_emit_scrive_nella_stessa_transazione(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.commit()
        rows = db_session.scalars(select(OutboxEvent)).all()
        assert len(rows) == 1
        assert rows[0].event_name == "struttura.creata"
        assert rows[0].delivered_at is None

    def test_rollback_annulla_anche_l_evento(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.rollback()
        assert db_session.scalars(select(OutboxEvent)).all() == []

    def test_evento_non_a_catalogo_rifiutato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        with pytest.raises(UnknownTypeError):
            emit(db_session, "entita.inventata", {}, catalog=test_catalog)

    def test_payload_non_conforme_rifiutato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        with pytest.raises(PayloadValidationError):
            emit(
                db_session,
                "struttura.creata",
                {"struttura_id": "x"},
                catalog=test_catalog,
            )


class TestDelivery:
    def test_consegna_dopo_il_commit_e_marca_delivered(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        ricevuti: list[tuple[str, dict]] = []
        subscribers = EventSubscribers()
        subscribers.subscribe(
            "struttura.creata",
            lambda session, name, payload: ricevuti.append((name, payload)),
        )

        payload = _payload()
        emit(db_session, "struttura.creata", payload, catalog=test_catalog)
        db_session.commit()

        consegnati = deliver_pending(db_session, subscribers)
        db_session.commit()

        assert consegnati == 1
        assert ricevuti == [("struttura.creata", payload)]
        evento = db_session.scalars(select(OutboxEvent)).one()
        assert evento.delivered_at is not None
        assert evento.attempts == 1

    def test_evento_gia_consegnato_non_viene_riconsegnato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        subscribers = EventSubscribers()
        chiamate: list[str] = []
        subscribers.subscribe("struttura.creata", lambda s, n, p: chiamate.append(n))
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.commit()

        deliver_pending(db_session, subscribers)
        db_session.commit()
        assert deliver_pending(db_session, subscribers) == 0
        assert len(chiamate) == 1

    def test_handler_fallito_lascia_l_evento_non_consegnato(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        subscribers = EventSubscribers()

        def handler_rotto(session: Session, name: str, payload: dict) -> None:
            raise RuntimeError("boom")

        subscribers.subscribe("struttura.creata", handler_rotto)
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.commit()

        consegnati = deliver_pending(db_session, subscribers)
        db_session.commit()

        assert consegnati == 0
        evento = db_session.scalars(select(OutboxEvent)).one()
        assert evento.delivered_at is None
        assert evento.attempts == 1

    def test_handler_che_scrive_e_poi_solleva_non_lascia_scritture_parziali(
        self, db_session: Session, test_catalog: Catalog
    ) -> None:
        # G-1 (AD-1/AD-10): atomicità per-item. L'handler scrive nella
        # sessione e POI fallisce: la scrittura parziale non deve essere
        # committata insieme al bookkeeping del fallimento.
        subscribers = EventSubscribers()

        def handler_scrivi_e_solleva(
            session: Session, name: str, payload: dict
        ) -> None:
            emit(session, "struttura.creata", _payload(), catalog=test_catalog)
            raise RuntimeError("boom dopo la scrittura")

        subscribers.subscribe("struttura.creata", handler_scrivi_e_solleva)
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.commit()

        consegnati = deliver_pending(db_session, subscribers)
        db_session.commit()

        assert consegnati == 0
        eventi = db_session.scalars(select(OutboxEvent)).all()
        assert len(eventi) == 1  # solo l'evento originale: niente orfani
        assert eventi[0].delivered_at is None
        assert eventi[0].attempts == 1  # il bookkeeping del tentativo resta

    def test_claim_concorrente_skip_locked(
        self,
        db_session: Session,
        second_session: Session,
        test_catalog: Catalog,
    ) -> None:
        subscribers = EventSubscribers()
        emit(db_session, "struttura.creata", _payload(), catalog=test_catalog)
        db_session.commit()

        # Il primo worker tiene il lock (transazione aperta): il secondo
        # deve saltare la riga, non bloccarsi né consegnarla due volte.
        consegnati_a = deliver_pending(db_session, subscribers)
        consegnati_b = deliver_pending(second_session, subscribers)
        db_session.commit()

        assert consegnati_a == 1
        assert consegnati_b == 0
