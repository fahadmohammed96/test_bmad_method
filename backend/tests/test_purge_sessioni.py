"""Test del purge delle sessioni scadute (G-5, AD-10, AD-15).

Il purge è un job DUREVOLE periodico sul kernel esistente: nessun timer
in memoria, handler idempotente, riprogrammazione dopo ogni esecuzione.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.core.jobs import Job, JobStatus
from app.identity.jobs import (
    TIPO_JOB_PURGE_SESSIONI,
    assicura_purge_periodico,
    purge_sessioni_scadute,
)
from app.identity.models import Host, Sessione


def _host(db: Session) -> Host:
    host = Host(email="host.di.prova@example.com", password_hash="$argon2id$finto")
    db.add(host)
    db.flush()
    return host


def _sessione(db: Session, host: Host, *, scaduta: bool, token: str) -> Sessione:
    sessione = Sessione(
        host_id=host.id,
        token_hash=token,
        expires_at=utcnow() + (timedelta(days=-1) if scaduta else timedelta(days=1)),
    )
    db.add(sessione)
    return sessione


class TestPurge:
    def test_elimina_le_scadute_e_lascia_intatte_le_valide(
        self, db_session: Session
    ) -> None:
        host = _host(db_session)
        _sessione(db_session, host, scaduta=True, token="hash-scaduta")
        _sessione(db_session, host, scaduta=False, token="hash-valida")
        db_session.commit()

        purge_sessioni_scadute(db_session, {})
        db_session.commit()

        rimaste = db_session.scalars(select(Sessione)).all()
        assert [s.token_hash for s in rimaste] == ["hash-valida"]

    def test_e_idempotente(self, db_session: Session) -> None:
        host = _host(db_session)
        _sessione(db_session, host, scaduta=True, token="hash-scaduta")
        _sessione(db_session, host, scaduta=False, token="hash-valida")
        db_session.commit()

        for _ in range(3):  # consegna at-least-once: rieseguire non cambia nulla
            purge_sessioni_scadute(db_session, {})
            db_session.commit()

        assert len(db_session.scalars(select(Sessione)).all()) == 1

    def test_senza_sessioni_scadute_non_fa_nulla(self, db_session: Session) -> None:
        host = _host(db_session)
        _sessione(db_session, host, scaduta=False, token="hash-valida")
        db_session.commit()

        purge_sessioni_scadute(db_session, {})
        db_session.commit()

        assert len(db_session.scalars(select(Sessione)).all()) == 1


class TestPeriodicita:
    def _job_pendenti(self, db: Session) -> list[Job]:
        return list(
            db.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_PURGE_SESSIONI,
                    Job.status == JobStatus.PENDING,
                )
            )
        )

    def test_l_esecuzione_riprogramma_il_prossimo_giro(
        self, db_session: Session
    ) -> None:
        # AD-10: la periodicità vive nella tabella `job`, mai in un timer
        # di processo — un restart non perde il ciclo.
        purge_sessioni_scadute(db_session, {})
        db_session.commit()

        pendenti = self._job_pendenti(db_session)
        assert len(pendenti) == 1
        assert pendenti[0].due_at > utcnow()

    def test_il_bootstrap_non_duplica_il_job(self, db_session: Session) -> None:
        assicura_purge_periodico(db_session)
        db_session.commit()
        assicura_purge_periodico(db_session)
        db_session.commit()

        assert len(self._job_pendenti(db_session)) == 1

    def test_il_bootstrap_riprende_dopo_un_riavvio_senza_job(
        self, db_session: Session
    ) -> None:
        assicura_purge_periodico(db_session)
        db_session.commit()
        for job in self._job_pendenti(db_session):
            db_session.delete(job)
        db_session.commit()

        assicura_purge_periodico(db_session)
        db_session.commit()
        assert len(self._job_pendenti(db_session)) == 1

    def test_il_tipo_di_job_e_a_catalogo(self) -> None:
        from app.core.events import catalog

        assert TIPO_JOB_PURGE_SESSIONI in catalog.job_names()
