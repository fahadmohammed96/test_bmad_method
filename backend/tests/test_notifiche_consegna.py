"""Story 2.6 — la notifica di Conflitto, dal fatto alla consegna.

Copre AC 1 (job durevole, mai silenziosa), AC 2 (alla PRIMA rilevazione),
AC 3 (at-least-once con handler idempotente), AC 6 (soli identificatori nei
payload, testo composto alla consegna), AC 7 (canale fallito ⇒ job
ritentabile, mai «inviata») e AC 8 (tentativi esauriti ⇒ `failed` osservabile).

Il percorso è quello vero e intero: si rileva un Conflitto, si consegna
l'evento `outbox` con il registro di PRODUZIONE, si eseguono i job con il
registro di produzione. Un `EventSubscribers` costruito nel test proverebbe
che l'handler fa il suo lavoro e tacerebbe sull'unica cosa che può davvero
mancare — la registrazione — che è la lezione della Story 2.5.

Nessun invio reale (AC 10): la fixture `isolamento_canale_email` del conftest
tiene il canale di produzione fuori portata, e chi ha bisogno di osservare un
invio installa un canale finto.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.calendario import service as calendario_service
from app.core.date_range import utcnow
from app.core.jobs import JobStatus, run_due_jobs
from app.core.outbox import OutboxEvent
from app.identity.models import CanaleNotifica
from app.notifiche.models import CanaleConsegna, StatoConsegna
from tests.calendario import (
    Contesto,
    conflitti,
    consegna_eventi,
    crea_prenotazione,
    registra_ospite,
)
from tests.notifiche import (
    consegna_su,
    consegne_di,
    installa_email_finta,
    job_di_consegna,
    notifiche_di,
    preferisci,
)

# Le due Prenotazioni si sovrappongono sulle notti 15-17 agosto: è l'esempio
# di `epics.md`, e serve a poterlo riconoscere nel testo consegnato.
PRIMA = (date(2026, 8, 12), date(2026, 8, 18))
SECONDA = (date(2026, 8, 15), date(2026, 8, 20))


def _rileva_conflitto(db: Session, contesto: Contesto) -> None:
    """Due Prenotazioni sovrapposte e la rilevazione che le trova (2.5)."""
    crea_prenotazione(db, contesto, check_in=PRIMA[0], check_out=PRIMA[1])
    crea_prenotazione(db, contesto, check_in=SECONDA[0], check_out=SECONDA[1])
    calendario_service.rivaluta_conflitti(db, contesto.host_id, contesto.struttura_id)
    db.commit()


def _esegui_job(db: Session, *, fra_ore: int = 0) -> int:
    eseguiti = run_due_jobs(db, now=utcnow() + timedelta(hours=fra_ore))
    db.commit()
    return eseguiti


class TestLaNotificaParte:
    """AC 1 — alla rilevazione parte una notifica, e passa da un job durevole."""

    def test_la_rilevazione_apre_una_notifica_e_accoda_un_job_per_canale(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        aperte = notifiche_di(db_session, contesto.host_id)
        assert len(aperte) == 1
        assert aperte[0].riferimento_id == conflitti(db_session, contesto)[0].id

        canali_serviti = {c.canale for c in consegne_di(db_session, contesto.host_id)}
        assert canali_serviti == {CanaleConsegna.IN_APP, CanaleConsegna.EMAIL}
        assert len(job_di_consegna(db_session)) == 2

    def test_niente_parte_dentro_la_transazione_che_rileva(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La rilevazione scrive il Conflitto e l'evento, e basta: se
        # notificasse in linea, un crash del processo fra la rilevazione e la
        # notifica sarebbe indistinguibile da un Conflitto mai rilevato — cioè
        # esattamente ciò che AD-10 vieta ai timer di processo.
        _rileva_conflitto(db_session, contesto)

        assert notifiche_di(db_session, contesto.host_id) == []
        assert job_di_consegna(db_session) == []

    def test_l_entrypoint_del_worker_registra_il_sottoscrittore_e_l_handler(
        self,
    ) -> None:
        # Classe «assenze»: se `app/worker.py` smettesse di importare il
        # cablaggio, gli eventi continuerebbero a essere scritti e
        # «consegnati» a zero handler, e nessun test funzionale cadrebbe. Si
        # guarda il registro di PRODUZIONE dopo l'import dell'entrypoint.
        import app.worker  # noqa: F401 — import con effetto di registrazione
        from app.cablaggio import al_conflitto_rilevato
        from app.core.jobs import handlers
        from app.core.outbox import subscribers
        from app.notifiche.jobs import TIPO_JOB_CONSEGNA_NOTIFICA

        assert al_conflitto_rilevato in subscribers.handlers_for(
            calendario_service.EVENTO_CONFLITTO_RILEVATO
        )
        assert handlers.handler_for(TIPO_JOB_CONSEGNA_NOTIFICA) is not None

    def test_la_consegna_in_app_scrive_il_messaggio_sulla_riga(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Per l'in-app la riga È la consegna: senza il testo, il canale
        # esisterebbe e non avrebbe niente da mostrare.
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        installa_email_finta()
        _esegui_job(db_session)

        in_app = consegna_su(db_session, contesto.host_id, CanaleConsegna.IN_APP)
        assert in_app is not None
        assert in_app.stato is StatoConsegna.INVIATA
        assert in_app.inviata_il is not None
        assert in_app.oggetto == (
            "Possibile doppia prenotazione — Appartamento di prova, 15-17 agosto"
        )
        assert "15-17 agosto" in (in_app.corpo or "")


class TestAllaPrimaRilevazione:
    """AC 2 — la notifica parte alla PRIMA rilevazione, non a ogni sync."""

    def test_una_seconda_rilevazione_dello_stesso_conflitto_non_rinotifica(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        # Un secondo giro di rilevazione: la 2.5 garantisce che non apra un
        # secondo Conflitto, e quindi non emette un secondo evento.
        calendario_service.rivaluta_conflitti(
            db_session, contesto.host_id, contesto.struttura_id
        )
        db_session.commit()
        consegna_eventi(db_session)

        assert len(notifiche_di(db_session, contesto.host_id)) == 1
        assert len(consegne_di(db_session, contesto.host_id)) == 2
        assert len(job_di_consegna(db_session)) == 2

    def test_lo_stesso_evento_consegnato_due_volte_non_apre_due_notifiche(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # At-least-once: un handler che fallisce più avanti nel batch fa
        # riprovare l'INTERO batch al tick successivo, quindi questo evento
        # viene riconsegnato. Non è un caso di laboratorio, è il regime.
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        db_session.execute(
            OutboxEvent.__table__.update().values(delivered_at=None, attempts=0)
        )
        db_session.commit()
        consegna_eventi(db_session)

        assert len(notifiche_di(db_session, contesto.host_id)) == 1
        assert len(job_di_consegna(db_session)) == 2


class TestIdempotenzaDellaConsegna:
    """AC 3 — at-least-once e handler idempotente sono una coppia."""

    def test_eseguire_due_volte_lo_stesso_job_manda_una_sola_email(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        email = installa_email_finta()
        _esegui_job(db_session)

        # Si rimette in coda il job già completato, che è ciò che accade a un
        # job ritentato dopo un fallimento più avanti nella transazione.
        for job in job_di_consegna(db_session):
            job.status = JobStatus.PENDING
        db_session.commit()
        _esegui_job(db_session)

        assert len(email.inviati) == 1, (
            "seconda email allo stesso Host per lo stesso Conflitto: è il modo "
            "in cui una notifica utile diventa rumore e l'Host smette di leggerle"
        )
        assert len(consegne_di(db_session, contesto.host_id)) == 2

    def test_il_destinatario_e_l_host_del_conflitto(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        email = installa_email_finta()
        _esegui_job(db_session)

        destinatario, _ = email.inviati[0]
        assert destinatario == "host.di.prova@example.com"


class TestSoliIdentificatori:
    """AC 6 — nei payload viaggiano identificatori; il testo nasce alla consegna."""

    def test_il_payload_del_job_porta_solo_identificatori(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        for job in job_di_consegna(db_session):
            assert set(job.payload) == {"consegna_id", "host_id"}
            assert all(isinstance(valore, str) for valore in job.payload.values())

    def test_il_testo_si_compone_alla_consegna_leggendo_lo_stato_corrente(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # La prova che il testo non è stato congelato alla richiesta: fra la
        # richiesta e la consegna cambia il nome della Struttura, e ciò che
        # arriva all'Host è il nome di ADESSO. Un testo scritto nel payload
        # sopravviverebbe in `job`, che è append-only, alla retention che
        # AD-21 impone ai dati che quel testo può contenere.
        from app.strutture.models import Struttura

        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        struttura = db_session.get(Struttura, contesto.struttura_id)
        assert struttura is not None
        struttura.nome = "Bologna Centro"
        db_session.commit()

        email = installa_email_finta()
        _esegui_job(db_session)

        _, messaggio = email.inviati[0]
        assert messaggio.oggetto == (
            "Possibile doppia prenotazione — Bologna Centro, 15-17 agosto"
        )

    def test_nessun_dato_dell_ospite_nel_testo_ne_nei_payload(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # È la prima volta che dati personali di TERZI attraversano `outbox`,
        # `job` e un messaggio in uscita (AD-16, NFR-11). I valori sono
        # inventati e restano inventati (NFR-16).
        nome_inventato = "Mario Rossi Inventato"
        prima = crea_prenotazione(
            db_session,
            contesto,
            check_in=PRIMA[0],
            check_out=PRIMA[1],
            sommario=f"Prenotazione di {nome_inventato}",
        )
        registra_ospite(
            db_session, contesto, prima, nome=nome_inventato, principale=True
        )
        crea_prenotazione(
            db_session, contesto, check_in=SECONDA[0], check_out=SECONDA[1]
        )
        calendario_service.rivaluta_conflitti(
            db_session, contesto.host_id, contesto.struttura_id
        )
        db_session.commit()
        consegna_eventi(db_session)
        email = installa_email_finta()
        _esegui_job(db_session)

        _, messaggio = email.inviati[0]
        assert nome_inventato not in messaggio.oggetto
        assert nome_inventato not in messaggio.corpo
        for job in job_di_consegna(db_session):
            assert nome_inventato not in str(job.payload)
        for consegna in consegne_di(db_session, contesto.host_id):
            assert nome_inventato not in f"{consegna.oggetto}{consegna.corpo}"


class TestUnCanaleCheFallisce:
    """AC 7 e AC 8 — nessuno stato di successo senza un esito reale."""

    def test_il_fallimento_lascia_il_job_ritentabile_e_la_consegna_in_attesa(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        installa_email_finta(fallisce=True)
        _esegui_job(db_session)

        email = consegna_su(db_session, contesto.host_id, CanaleConsegna.EMAIL)
        assert email is not None
        assert email.stato is StatoConsegna.IN_ATTESA, (
            "consegna marcata «inviata» senza che il canale abbia consegnato"
        )
        assert email.inviata_il is None

        job_email = [
            job
            for job in job_di_consegna(db_session)
            if job.payload["consegna_id"] == str(email.id)
        ][0]
        assert job_email.status is JobStatus.PENDING
        assert job_email.attempts == 1
        assert job_email.last_error is not None
        assert job_email.due_at > utcnow()

    def test_il_canale_rotto_non_trascina_quello_che_funziona(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Un job per canale: l'email che fallisce non deve far annullare la
        # consegna in-app già marcata. Se fossero un job solo, il SAVEPOINT
        # del kernel le annullerebbe entrambe e l'Host resterebbe cieco su un
        # Conflitto per un guasto del relay di posta.
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        installa_email_finta(fallisce=True)
        _esegui_job(db_session)

        in_app = consegna_su(db_session, contesto.host_id, CanaleConsegna.IN_APP)
        assert in_app is not None
        assert in_app.stato is StatoConsegna.INVIATA

    def test_esauriti_i_tentativi_il_job_resta_visibile_come_failed(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Il silenzio è il difetto: una notifica che non parte e non lascia
        # traccia è indistinguibile da un Conflitto che non c'è.
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        installa_email_finta(fallisce=True)

        email = consegna_su(db_session, contesto.host_id, CanaleConsegna.EMAIL)
        assert email is not None
        job_email = [
            job
            for job in job_di_consegna(db_session)
            if job.payload["consegna_id"] == str(email.id)
        ][0]
        for tentativo in range(job_email.max_attempts):
            _esegui_job(db_session, fra_ore=24 * (tentativo + 1))

        db_session.refresh(job_email)
        db_session.refresh(email)
        assert job_email.status is JobStatus.FAILED
        assert job_email.attempts == job_email.max_attempts
        assert job_email.last_error is not None
        assert email.stato is StatoConsegna.IN_ATTESA

    def test_il_motivo_del_fallimento_non_porta_il_testo_ne_il_destinatario(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # `job.last_error` è una colonna che nessuno ripulisce: ci va la
        # categoria dell'errore, mai il contenuto (AD-16, NFR-11).
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)
        installa_email_finta(fallisce=True)
        _esegui_job(db_session)

        motivi = [
            job.last_error
            for job in job_di_consegna(db_session)
            if job.last_error is not None
        ]
        assert motivi
        for motivo in motivi:
            assert "host.di.prova@example.com" not in motivo
            assert "doppia prenotazione" not in motivo


class TestNotificaSenzaFatto:
    """Il riferimento che non esiste: si solleva, non si tace."""

    def test_una_notifica_su_un_conflitto_inesistente_non_si_consegna(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        import uuid

        from app.cablaggio import TIPO_NOTIFICA_CONFLITTO_RILEVATO
        from app.notifiche import service as notifiche_service
        from app.notifiche.registro import FattoScomparsoError

        notifica = notifiche_service.richiedi(
            db_session,
            contesto.host_id,
            tipo=TIPO_NOTIFICA_CONFLITTO_RILEVATO,
            riferimento_id=uuid.uuid4(),
        )
        assert notifica is not None
        db_session.commit()

        consegna = consegne_di(db_session, contesto.host_id)[0]
        with pytest.raises(FattoScomparsoError):
            notifiche_service.consegna(db_session, contesto.host_id, consegna.id)

    def test_un_tipo_di_notifica_senza_compositore_e_rifiutato(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-17: un tipo inventato ad hoc non deve poter produrre una riga che
        # nessun job potrà mai consegnare.
        import uuid

        from app.notifiche import service as notifiche_service
        from app.notifiche.registro import TipoNotificaSconosciutoError

        with pytest.raises(TipoNotificaSconosciutoError):
            notifiche_service.richiedi(
                db_session,
                contesto.host_id,
                tipo="inventato_al_volo",
                riferimento_id=uuid.uuid4(),
            )
        assert notifiche_di(db_session, contesto.host_id) == []


class TestConflittoSenzaSovrapposizione:
    """Il portale sposta le date: il Conflitto resta, l'intervallo no."""

    def test_non_si_inventa_un_intervallo_quando_la_sovrapposizione_e_sparita(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Raggiungibile: il decadimento ha una sola causa, l'uscita da
        # `attiva` (AD-5, AD-19), quindi uno spostamento di date lascia il
        # Conflitto aperto su due soggiorni che non si toccano più.
        prima = crea_prenotazione(
            db_session, contesto, check_in=PRIMA[0], check_out=PRIMA[1]
        )
        crea_prenotazione(
            db_session, contesto, check_in=SECONDA[0], check_out=SECONDA[1]
        )
        calendario_service.rivaluta_conflitti(
            db_session, contesto.host_id, contesto.struttura_id
        )
        db_session.commit()
        consegna_eventi(db_session)

        prima.check_out = date(2026, 8, 14)
        db_session.commit()

        installa_email_finta()
        _esegui_job(db_session)

        # Il job non consegna e resta ritentabile con il motivo scritto: il
        # percorso passa dal kernel, che converte l'eccezione in un
        # fallimento tracciato invece di lasciarla risalire.
        for consegna in consegne_di(db_session, contesto.host_id):
            assert consegna.stato is StatoConsegna.IN_ATTESA
        motivi = [job.last_error for job in job_di_consegna(db_session)]
        assert all(
            motivo is not None and "ConflittoSenzaSovrapposizione" in motivo
            for motivo in motivi
        )


class TestPreferenzeIgnorate:
    """AC 5 sul percorso intero: la preferenza governa i canali in uscita."""

    def test_con_preferenza_in_app_nessuna_email_parte(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        preferisci(db_session, contesto.host_id, CanaleNotifica.IN_APP)
        db_session.commit()
        _rileva_conflitto(db_session, contesto)
        consegna_eventi(db_session)

        canali_serviti = {c.canale for c in consegne_di(db_session, contesto.host_id)}
        assert canali_serviti == {CanaleConsegna.IN_APP}
        assert len(job_di_consegna(db_session)) == 1

        # La guardia del conftest solleva se qualcuno tocca il canale email:
        # qui il test passa proprio perché nessuno lo tocca.
        _esegui_job(db_session)
        in_app = consegna_su(db_session, contesto.host_id, CanaleConsegna.IN_APP)
        assert in_app is not None
        assert in_app.stato is StatoConsegna.INVIATA
