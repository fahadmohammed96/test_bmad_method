"""Retention della coda `job` (MYL-51).

Dalla Story 2.2 `job` cresce senza limite e a ritmo noto, e nessuna riga
veniva mai eliminata. Il difetto è **silenzioso**: nessun errore, nessun test
rosso, solo una tabella che diventa lentamente più grande e query che
diventano lentamente più lente. Si chiude adesso perché adesso costa poco.

Le proprietà pinnate qui sono tre, e la terza è quella che si dimentica:

1. il purge elimina ciò che deve e **solo** ciò che deve — in particolare non
   tocca le righe `failed`, il cui `last_error` è spesso l'unica traccia
   rimasta di un guasto;
2. è idempotente — la consegna dei job è at-least-once (AD-10);
3. il ciclo **non si spegne da solo** se la `DELETE` fallisce. È il difetto
   E2-F1, già visto sulla retention dell'anagrafica Ospite: l'eccezione porta
   il job a `failed` al quinto tentativo, in coda non resta nessun purge, e la
   tabella torna a crescere senza limite fino al prossimo riavvio del worker —
   cioè il difetto che questo modulo esiste per chiudere, reintrodotto dal suo
   stesso rimedio.
"""

from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.date_range import utcnow
from app.core.db import new_uuid7
from app.core.events import catalog
from app.core.jobs import Job, JobStatus, run_due_jobs
from app.core.manutenzione import (
    TIPO_JOB_PURGE_JOB,
    assicura_purge_job_periodico,
    purga_job_completati,
)

# Un tipo qualunque: il purge decide su stato ed età, mai sul tipo.
TIPO_QUALUNQUE = "promemoria.invia"

FINESTRA = 30


def _job(db: Session, *, stato: JobStatus, giorni_fa: int) -> Job:
    """Una riga di coda con un'età decisa dal test.

    `created_at` si scrive esplicitamente: è il campo su cui la retention
    decide, e lasciarlo al default renderebbe ogni riga «di oggi».
    """
    quando = utcnow() - timedelta(days=giorni_fa)
    job = Job(
        id=new_uuid7(),
        job_type=TIPO_QUALUNQUE,
        payload={"adempimento_id": "finto"},
        due_at=quando,
        status=stato,
        created_at=quando,
    )
    db.add(job)
    db.flush()
    return job


def _stati_superstiti(db: Session) -> list[JobStatus]:
    db.expire_all()
    return [
        job.status
        for job in db.scalars(select(Job).where(Job.job_type == TIPO_QUALUNQUE))
    ]


@pytest.fixture(autouse=True)
def finestra_di_trenta_giorni(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOSTPILOT_JOB_RETENTION_GIORNI", str(FINESTRA))
    get_settings.cache_clear()


class TestCosaSiElimina:
    def test_elimina_le_completate_oltre_la_finestra(self, db_session: Session) -> None:
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=FINESTRA + 1)
        db_session.commit()

        purga_job_completati(db_session, {})
        db_session.commit()

        assert _stati_superstiti(db_session) == []

    def test_lascia_le_completate_DENTRO_la_finestra(self, db_session: Session) -> None:
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=FINESTRA - 1)
        db_session.commit()

        purga_job_completati(db_session, {})
        db_session.commit()

        assert _stati_superstiti(db_session) == [JobStatus.COMPLETED]

    def test_non_tocca_le_fallite_per_quanto_vecchie(self, db_session: Session) -> None:
        # LA riga che questo test difende. Le `failed` sono poche, il loro
        # numero è un sintomo e il loro `last_error` è spesso l'unica cosa che
        # resta di un guasto: cancellarle sarebbe buttare l'evidenza di un
        # problema aperto per recuperare spazio che non occupano.
        _job(db_session, stato=JobStatus.FAILED, giorni_fa=FINESTRA * 10)
        db_session.commit()

        purga_job_completati(db_session, {})
        db_session.commit()

        assert _stati_superstiti(db_session) == [JobStatus.FAILED]

    def test_non_tocca_il_lavoro_in_corso_o_futuro(self, db_session: Session) -> None:
        # Una `pending` molto vecchia esiste: è un job scaduto che il worker
        # non ha ancora preso, o un ciclo periodico rimasto indietro. Non è
        # storia, è lavoro da fare.
        _job(db_session, stato=JobStatus.PENDING, giorni_fa=FINESTRA * 10)
        _job(db_session, stato=JobStatus.RUNNING, giorni_fa=FINESTRA * 10)
        db_session.commit()

        purga_job_completati(db_session, {})
        db_session.commit()

        assert sorted(stato.value for stato in _stati_superstiti(db_session)) == [
            "pending",
            "running",
        ]

    def test_e_idempotente(self, db_session: Session) -> None:
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=FINESTRA + 1)
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=1)
        db_session.commit()

        for _ in range(3):  # consegna at-least-once: rieseguire non cambia nulla
            purga_job_completati(db_session, {})
            db_session.commit()

        assert _stati_superstiti(db_session) == [JobStatus.COMPLETED]

    def test_il_conteggio_finisce_nel_log(
        self, db_session: Session, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Un purge che non dice quante righe ha tolto è indistinguibile da uno
        # che non ha girato. `extra=` non finisce in `caplog.text`: si asserisce
        # sull'attributo del record.
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=FINESTRA + 1)
        db_session.commit()

        with caplog.at_level("INFO", logger="app.core.manutenzione"):
            purga_job_completati(db_session, {})
        db_session.commit()

        eliminati = [
            record.job_eliminati
            for record in caplog.records
            if hasattr(record, "job_eliminati")
        ]
        assert eliminati == [1]


class TestLaPeriodicita:
    def _in_coda(self, db: Session) -> list[Job]:
        return list(
            db.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_PURGE_JOB,
                    Job.status == JobStatus.PENDING,
                )
            )
        )

    def test_l_esecuzione_riprogramma_il_prossimo_giro(
        self, db_session: Session
    ) -> None:
        purga_job_completati(db_session, {})
        db_session.commit()

        in_coda = self._in_coda(db_session)
        assert len(in_coda) == 1
        # Nel FUTURO: un ciclo periodico già scaduto alla nascita verrebbe
        # preso nello stesso giro di worker che l'ha creato.
        assert in_coda[0].due_at > utcnow()

    def test_il_tipo_di_job_e_a_catalogo(self) -> None:
        assert TIPO_JOB_PURGE_JOB in catalog.job_names()


class TestIlCicloNonSiSpegneDaSolo:
    """E2-F1 applicato al purge della coda.

    Il `try/except` da solo non basterebbe: l'handler gira dentro il SAVEPOINT
    per item di `run_due_jobs` (G-1), quindi una riprogrammazione scritta in un
    `finally` verrebbe annullata insieme all'eccezione, e se a fallire è la
    query la transazione resta abortita e anche l'`INSERT` fallirebbe.
    """

    def _in_coda(self, db: Session) -> list[Job]:
        return list(
            db.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_PURGE_JOB,
                    Job.status == JobStatus.PENDING,
                )
            )
        )

    def test_un_errore_DEL_DATABASE_non_spegne_il_ciclo(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.core.manutenzione.filtro_scaduti",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        purga_job_completati(db_session, {})
        db_session.commit()

        assert len(self._in_coda(db_session)) == 1, (
            "dopo un errore la coda è rimasta senza purge: la tabella `job` "
            "tornerebbe a crescere senza limite fino al prossimo riavvio"
        )

    def test_un_errore_PRIMA_della_delete_non_spegne_il_ciclo(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def esplode(_limite: object) -> object:
            raise RuntimeError("guasto simulato prima della DELETE")

        monkeypatch.setattr("app.core.manutenzione.filtro_scaduti", esplode)

        purga_job_completati(db_session, {})
        db_session.commit()

        assert len(self._in_coda(db_session)) == 1

    def test_il_fallimento_e_VISIBILE_non_silenzioso(
        self,
        db_session: Session,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Una manutenzione non eseguita che non lascia traccia è
        # indistinguibile da una eseguita su zero righe.
        monkeypatch.setattr(
            "app.core.manutenzione.filtro_scaduti",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        with caplog.at_level("ERROR", logger="app.core.manutenzione"):
            purga_job_completati(db_session, {})
        db_session.commit()

        assert any("non eseguito" in record.message for record in caplog.records)

    def test_dopo_un_giro_fallito_il_giro_dopo_elimina_davvero(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _job(db_session, stato=JobStatus.COMPLETED, giorni_fa=FINESTRA + 1)
        db_session.commit()
        monkeypatch.setattr(
            "app.core.manutenzione.filtro_scaduti",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )
        purga_job_completati(db_session, {})
        db_session.commit()
        monkeypatch.undo()

        purga_job_completati(db_session, {})
        db_session.commit()

        assert _stati_superstiti(db_session) == []

    def test_il_worker_non_manda_il_purge_a_failed_per_un_guasto_della_delete(
        self, db_session: Session, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Il percorso REALE, non l'handler chiamato a mano: `run_due_jobs`
        # esegue dentro il SAVEPOINT per item, ed è lì che il difetto nasce.
        assicura_purge_job_periodico(db_session)
        db_session.commit()
        monkeypatch.setattr(
            "app.core.manutenzione.filtro_scaduti",
            lambda _limite: text("colonna_che_non_esiste > 1"),
        )

        for _ in range(5):
            prossimo = db_session.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_PURGE_JOB,
                    Job.status == JobStatus.PENDING,
                )
            ).first()
            assert prossimo is not None, "il ciclo di purge si è spento"
            run_due_jobs(db_session, now=prossimo.due_at)
            db_session.commit()

        assert (
            db_session.scalars(
                select(Job).where(
                    Job.job_type == TIPO_JOB_PURGE_JOB,
                    Job.status == JobStatus.FAILED,
                )
            ).all()
            == []
        )


class TestIParametriDiConfigurazione:
    """Validati su `Settings`, non solo nel codice che li consuma.

    Altrimenti `import app.main` riesce con un valore assurdo e il difetto si
    manifesta a regime, quando qualcuno collega il sintomo alla causa.
    """

    @pytest.mark.parametrize("giorni", [0, -1])
    def test_una_finestra_non_positiva_ferma_l_avvio(self, giorni: int) -> None:
        # Zero giorni eliminerebbe i job appena completati: la coda perderebbe
        # la propria storia recente proprio mentre serve a diagnosticare.
        with pytest.raises(ValidationError):
            Settings(job_retention_giorni=giorni)

    @pytest.mark.parametrize("minuti", [0, -1])
    def test_un_intervallo_non_positivo_ferma_l_avvio(self, minuti: int) -> None:
        # Un intervallo di 0 minuti riaccoda il purge già scaduto e il worker
        # gira in ciclo stretto, consumando la coda di tutti i tenant.
        with pytest.raises(ValidationError):
            Settings(job_retention_intervallo_minuti=minuti)
