"""Story 2.2 — il poller periodico, su PostgreSQL reale.

Copre gli AC 1, 2, 6, 7, 8, 9, 11 e 12 del test design §3. Il kernel AD-10 è
già coperto dall'Epic 1 (`test_jobs.py`): qui si prova **l'aggancio del
dominio**, sul modello già validato di `test_purge_sessioni.py`.

Due proprietà che si rompono in modi opposti e vanno provate separatamente:

- senza la **riprogrammazione**, il poller gira una volta sola;
- senza il **bootstrap**, un ciclo perso non torna mai.

Il tempo si inietta o si scrive nel passato con `utcnow() ± timedelta`: mai
uno `sleep` per attendere una scadenza (test design §5.4). Il riavvio del
worker si SIMULA rieseguendo il bootstrap, non spegnendo un processo.

Nessun dato reale di Ospiti nei fixture (NFR-16); rete stub-ata al trasporto.
"""

import logging
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.jobs import (
    TIPO_JOB_SYNC_FEED,
    TIPO_JOB_SYNC_PERIODICO,
    assicura_sync_periodico,
    bootstrap_sync_periodico,
    esegui_sync_periodico,
)
from app.calendario.models import (
    CategoriaErroreSync,
    EsitoSyncRun,
    FeedIcal,
    Prenotazione,
    StatoPrenotazione,
)
from app.calendario.schemas import StatoSincronizzazione
from app.core.config import get_settings
from app.core.date_range import today_rome, utcnow
from app.core.jobs import Job, JobStatus, handlers, run_due_jobs
from tests.calendario import (
    Contesto,
    calendario,
    client,
    collega,
    crea_host,
    crea_struttura,
    prenotazioni,
    sincronizza,
    vevent,
)
from tests.server_feed import RispostaPreparata, ServerFeed

PERCORSO = "/calendario.ics"

DUE_EVENTI = calendario(
    vevent("uid-1@example.com", dal="20260810", al="20260812"),
    vevent("uid-2@example.com", dal="20260901", al="20260903"),
)


def job_periodici(db: Session, feed: FeedIcal | None = None) -> list[Job]:
    istruzione = select(Job).where(
        Job.job_type == TIPO_JOB_SYNC_PERIODICO,
        Job.status.in_((JobStatus.PENDING, JobStatus.RUNNING)),
    )
    if feed is not None:
        istruzione = istruzione.where(Job.payload["feed_id"].astext == str(feed.id))
    return list(db.scalars(istruzione))


@pytest.fixture(autouse=True)
def rete_verso_il_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ammette il loopback nella politica di uscita di rete, per tutto il file.

    Il poller passa dall'handler, e l'handler usa `client_di_produzione()`:
    la politica arriva dalla CONFIGURAZIONE, non da un client iniettato. Senza
    il loopback ammesso ogni fetch verso il server di test verrebbe rifiutato
    a monte, e il rifiuto produce `url_non_raggiungibile` — cioè esattamente
    uno degli esiti che alcuni test qui vogliono osservare.

    È autouse per questo: un test che passasse perché la rete è stata
    rifiutata, invece che perché il portale ha risposto come previsto,
    sarebbe verde e non proverebbe nulla. La prima stesura di questo file ne
    aveva uno.
    """
    monkeypatch.setenv("HOSTPILOT_FEED_RETI_CONSENTITE", "127.0.0.0/8")
    get_settings.cache_clear()


@pytest.fixture
def feed_pronto(
    db_session: Session, contesto: Contesto, server_feed: ServerFeed
) -> FeedIcal:
    server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))
    return collega(db_session, contesto, server_feed.url(PERCORSO))


class TestUnCicloDurevolePerFeed:
    """AC 1 (P0) — job durevole a intervallo configurabile, mai un timer."""

    def test_collegare_un_feed_accoda_subito_anche_il_ciclo_periodico(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # Affidare il primo giro al bootstrap del worker significherebbe che
        # un Feed collegato oggi comincia a risincronizzarsi al prossimo
        # rilascio.
        accodati = job_periodici(db_session, feed_pronto)
        assert len(accodati) == 1
        assert accodati[0].payload == {
            "feed_id": str(feed_pronto.id),
            "host_id": str(feed_pronto.host_id),
        }

    def test_il_ciclo_periodico_nasce_SEMPRE_nel_futuro(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # Un ciclo già scaduto alla nascita verrebbe preso nello stesso giro
        # di worker che l'ha creato, e il poller girerebbe in ciclo stretto.
        # È anche la proprietà su cui poggia la priorità dell'on-demand.
        assert job_periodici(db_session, feed_pronto)[0].due_at > utcnow()

    def test_l_import_on_demand_precede_ancora_i_cicli_periodici(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        scaduti = db_session.scalars(
            select(Job).where(Job.due_at <= utcnow(), Job.status == JobStatus.PENDING)
        ).all()
        assert [job.job_type for job in scaduti] == [TIPO_JOB_SYNC_FEED]

    def test_l_intervallo_arriva_dalla_CONFIGURAZIONE(
        self,
        db_session: Session,
        contesto: Contesto,
        server_feed: ServerFeed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # «Configurabile» si prova cambiando il parametro e vedendo cambiare
        # il `due_at`: altrimenti è una parola del documento. La fixture
        # autouse `configurazione_pulita` svuota la cache di `get_settings`.
        monkeypatch.setenv("HOSTPILOT_FEED_SYNC_INTERVALLO_MINUTI", "90")
        get_settings.cache_clear()
        server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))

        prima = utcnow()
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        atteso = prima + timedelta(minutes=90)
        job = job_periodici(db_session, feed)[0]
        assert (
            atteso - timedelta(minutes=1) <= job.due_at <= atteso + timedelta(minutes=1)
        )

    def test_il_tipo_di_job_e_a_catalogo(self) -> None:
        from app.core.events import catalog

        assert TIPO_JOB_SYNC_PERIODICO in catalog.job_names()

    def test_il_payload_porta_solo_identificatori(self) -> None:
        from app.core.events import catalog

        assert catalog.job(TIPO_JOB_SYNC_PERIODICO).payload_keys == frozenset(
            {"feed_id", "host_id"}
        )

    def test_esiste_un_handler_registrato(self) -> None:
        # Un job a catalogo senza handler si accoda e poi muore per
        # `LookupError` a ogni tentativo: il ciclo sarebbe rotto in un modo
        # che solo i log del worker raccontano.
        assert handlers.handler_for(TIPO_JOB_SYNC_PERIODICO) is not None


class TestRiprogrammazione:
    """AC 1 e 12 — l'handler rimette in coda il giro successivo. Sempre."""

    def test_un_giro_riuscito_riprogramma_il_prossimo(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        precedente = job_periodici(db_session, feed_pronto)[0]
        db_session.delete(precedente)
        db_session.commit()

        esegui_sync_periodico(
            db_session,
            {
                "feed_id": str(feed_pronto.id),
                "host_id": str(feed_pronto.host_id),
            },
        )
        db_session.commit()

        accodati = job_periodici(db_session, feed_pronto)
        assert len(accodati) == 1
        assert accodati[0].due_at > utcnow()
        assert len(prenotazioni(db_session, feed_pronto)) == 2

    def test_un_giro_FALLITO_riprogramma_lo_stesso(
        self, db_session: Session, server_feed: ServerFeed, feed_pronto: FeedIcal
    ) -> None:
        # È il punto di NFR-1: un portale irraggiungibile per un'ora non deve
        # spegnere il poller di quel Feed, altrimenti il primo guasto
        # temporaneo diventa permanente e non lo scopre nessuno.
        for job in job_periodici(db_session, feed_pronto):
            db_session.delete(job)
        db_session.commit()
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))

        esegui_sync_periodico(
            db_session,
            {
                "feed_id": str(feed_pronto.id),
                "host_id": str(feed_pronto.host_id),
            },
        )
        db_session.commit()

        assert (
            service.ultimo_run(db_session, feed_pronto.host_id, feed_pronto.id).esito
            is EsitoSyncRun.FALLITO
        )
        assert len(job_periodici(db_session, feed_pronto)) == 1

    def test_un_feed_scomparso_ferma_il_ciclo_invece_di_riaccodarlo(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # L'unica uscita legittima senza riprogrammazione: continuare ad
        # accodare su una risorsa che non esiste più sarebbe una coda che
        # cresce per sempre.
        esegui_sync_periodico(
            db_session,
            {
                "feed_id": str(uuid.uuid4()),
                "host_id": str(contesto.host_id),
            },
        )
        db_session.commit()

        assert job_periodici(db_session) == []

    def test_il_ciclo_gira_davvero_attraverso_il_worker(
        self, db_session: Session, server_feed: ServerFeed, feed_pronto: FeedIcal
    ) -> None:
        # Non l'handler chiamato a mano: il claim del kernel, con il job
        # scritto nel passato invece che atteso.
        run_due_jobs(db_session)  # consuma l'import on-demand
        db_session.commit()
        periodico = job_periodici(db_session, feed_pronto)[0]
        periodico.due_at = utcnow() - timedelta(seconds=1)
        db_session.commit()

        completati = run_due_jobs(db_session)
        db_session.commit()

        assert completati == 1
        assert db_session.get(Job, periodico.id).status is JobStatus.COMPLETED
        successivo = job_periodici(db_session, feed_pronto)
        assert len(successivo) == 1
        assert successivo[0].id != periodico.id


class TestBootstrapIdempotente:
    """AC 2 (P0) — un solo job in coda per Feed, anche dopo un riavvio."""

    def test_il_bootstrap_non_duplica_il_ciclo(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        for _ in range(3):
            assicura_sync_periodico(db_session, feed_pronto)
            db_session.commit()

        assert len(job_periodici(db_session, feed_pronto)) == 1

    def test_il_riavvio_del_worker_non_duplica_nulla(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # Il riavvio si SIMULA rieseguendo il bootstrap: spegnere un processo
        # proverebbe qualcosa sul sistema operativo, non sul codice.
        assert bootstrap_sync_periodico(db_session) == 0
        db_session.commit()

        assert len(job_periodici(db_session, feed_pronto)) == 1

    def test_il_bootstrap_riprende_un_ciclo_perso(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # Un job andato a `failed` per esaurimento dei tentativi, o una riga
        # cancellata a mano: senza questa rete di sicurezza il Feed
        # smetterebbe di aggiornarsi in silenzio.
        for job in job_periodici(db_session, feed_pronto):
            db_session.delete(job)
        db_session.commit()

        assert bootstrap_sync_periodico(db_session) == 1
        db_session.commit()

        assert len(job_periodici(db_session, feed_pronto)) == 1

    def test_un_ciclo_ESAURITO_viene_ripreso(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        job = job_periodici(db_session, feed_pronto)[0]
        job.status = JobStatus.FAILED
        db_session.commit()

        assert bootstrap_sync_periodico(db_session) == 1
        db_session.commit()

        assert len(job_periodici(db_session, feed_pronto)) == 1

    def test_il_bootstrap_copre_i_feed_di_TUTTI_gli_host(
        self, db_session: Session, server_feed: ServerFeed
    ) -> None:
        # La query non è scopata per Host di proposito: all'avvio del worker
        # non esiste un Host «corrente», e scoparla significherebbe non
        # sincronizzare i Feed di tutti gli altri.
        server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))
        feed = []
        for indice in range(3):
            host = crea_host(db_session, f"host.{indice}.di.prova@example.com")
            struttura = crea_struttura(db_session, host.id, f"Appartamento {indice}")
            db_session.commit()
            feed.append(
                collega(
                    db_session,
                    Contesto(host_id=host.id, struttura_id=struttura.id),
                    server_feed.url(PERCORSO),
                )
            )
        for job in job_periodici(db_session):
            db_session.delete(job)
        db_session.commit()

        assert bootstrap_sync_periodico(db_session) == 3
        db_session.commit()

        for riga in feed:
            assert len(job_periodici(db_session, riga)) == 1

    def test_il_bootstrap_dell_avvio_accoda_anche_il_purge(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # `app.worker.bootstrap_job_periodici` fa entrambi in UNA
        # transazione: se il poller fallisce, il purge non deve restare
        # accodato da solo dando l'impressione che l'avvio sia riuscito.
        from app.identity.jobs import TIPO_JOB_PURGE_SESSIONI, assicura_purge_periodico

        assicura_purge_periodico(db_session)
        bootstrap_sync_periodico(db_session)
        db_session.commit()

        tipi = {
            job.job_type
            for job in db_session.scalars(
                select(Job).where(Job.status == JobStatus.PENDING)
            )
        }
        assert TIPO_JOB_PURGE_SESSIONI in tipi
        assert TIPO_JOB_SYNC_PERIODICO in tipi

    def test_l_ENTRYPOINT_del_worker_accoda_tutti_i_cicli(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        """P1-4: `app.worker.bootstrap_job_periodici` eseguito davvero.

        Il test sopra chiama a mano le due funzioni, quindi non dice nulla
        sull'entrypoint che le compone: togliere
        `calendario_jobs.bootstrap_sync_periodico(db)` da `app/worker.py`
        lasciava la suite verde, e l'unica cosa che se ne accorgeva era `F401`
        di ruff — un cancello di lint, non di comportamento.

        Il modo di guasto che questo copre e' preciso: il worker riparte, i
        cicli non vengono riaccodati, e i Feed smettono di aggiornarsi in
        silenzio. E' la cosa che questa Story esiste per impedire.
        """
        from app import worker
        from app.calendario.jobs import TIPO_JOB_RETENTION_OSPITE
        from app.identity.jobs import TIPO_JOB_PURGE_SESSIONI

        for job in db_session.scalars(select(Job)):
            db_session.delete(job)
        db_session.commit()

        # Nessun argomento: apre la propria sessione e committa da se', come
        # all'avvio del processo. Per questo dopo si rilegge da capo.
        worker.bootstrap_job_periodici()

        db_session.expire_all()
        tipi = [
            job.job_type
            for job in db_session.scalars(
                select(Job).where(Job.status == JobStatus.PENDING)
            )
        ]
        # Uguaglianza esatta, non contenimento: un ciclo periodico nuovo che
        # nessuno accoda all'avvio è la stessa assenza silenziosa, e qui deve
        # far fallire chi lo aggiunge senza toccare l'entrypoint.
        assert sorted(tipi) == sorted(
            [
                TIPO_JOB_PURGE_SESSIONI,
                TIPO_JOB_SYNC_PERIODICO,
                TIPO_JOB_RETENTION_OSPITE,
            ]
        )


class TestIntervalloDelPollerSulDatabASE:
    """P1-2 — la COMPOSIZIONE fra la lettura di stato e la regola pura.

    `intervallo.py` e' coperto da 14 test unit e regge; `prossimo_check_in` e
    `intervallo_prossimo_sync` non erano coperti affatto. Il difetto viveva
    esattamente li': la funzione pura e' corretta, la query le passava
    l'argomento sbagliato, e nessun test guardava il punto in cui le due si
    incontrano.
    """

    def _prenota(
        self,
        db: Session,
        feed: FeedIcal,
        *,
        check_in: date,
        stato=StatoPrenotazione.ATTIVA,
    ) -> None:
        db.add(
            Prenotazione(
                host_id=feed.host_id,
                struttura_id=feed.struttura_id,
                feed_id=feed.id,
                ical_uid=f"uid-{check_in.isoformat()}-{stato.value}@example.com",
                canale=feed.canale,
                check_in=check_in,
                check_out=check_in + timedelta(days=2),
                stato=stato,
            )
        )
        db.flush()

    def test_senza_prenotazioni_l_intervallo_e_quello_pieno(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=15)

    def test_un_check_in_domani_stringe_il_ritmo(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        self._prenota(
            db_session, feed_pronto, check_in=today_rome() + timedelta(days=1)
        )

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=5)

    def test_un_check_in_OGGI_non_oscura_quello_di_DOMANI(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # IL difetto (P1-1 di Murat sul merito, P1-2 nel suo elenco). Il
        # check-in di oggi e' gia' iniziato — la mezzanotte e' passata — quindi
        # non stringe niente; ma essendo il PRIMO in ordine di data prendeva il
        # `LIMIT 1` e oscurava quello di domani, riportando l'intervallo al
        # pieno. L'AC 10 si invertiva nel giorno di massima occupazione, cioe'
        # quello in cui una cancellazione tardiva non vista costa di piu'.
        self._prenota(db_session, feed_pronto, check_in=today_rome())
        self._prenota(
            db_session, feed_pronto, check_in=today_rome() + timedelta(days=1)
        )

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=5)

    def test_un_check_in_solo_OGGI_lascia_il_ritmo_pieno(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # L'altra meta': la correzione non deve trasformare «oggi» in un
        # motivo per accelerare. La finestra e' quella che PRECEDE l'arrivo.
        self._prenota(db_session, feed_pronto, check_in=today_rome())

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=15)

    def test_un_check_in_lontano_lascia_il_ritmo_pieno(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        self._prenota(
            db_session, feed_pronto, check_in=today_rome() + timedelta(days=30)
        )

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=15)

    @pytest.mark.parametrize(
        "stato", [StatoPrenotazione.CANCELLATA, StatoPrenotazione.RIMOSSA_DAL_FEED]
    )
    def test_una_prenotazione_non_attiva_non_stringe_il_ritmo(
        self, db_session: Session, feed_pronto: FeedIcal, stato: StatoPrenotazione
    ) -> None:
        # Un arrivo cancellato non e' un arrivo: trattarlo come tale terrebbe
        # un Feed morto sul ritmo stretto per sempre.
        self._prenota(
            db_session,
            feed_pronto,
            check_in=today_rome() + timedelta(days=1),
            stato=stato,
        )

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=15)

    def test_il_check_in_di_un_ALTRA_struttura_non_stringe_il_ritmo(
        self, db_session: Session, contesto: Contesto, feed_pronto: FeedIcal
    ) -> None:
        # La query e' scopata per Struttura oltre che per Host: l'arrivo di un
        # altro appartamento non e' un motivo per interrogare questo portale.
        altra = crea_struttura(db_session, contesto.host_id, "Altro appartamento")
        db_session.add(
            Prenotazione(
                host_id=contesto.host_id,
                struttura_id=altra.id,
                ical_uid=None,
                canale=feed_pronto.canale,
                check_in=today_rome() + timedelta(days=1),
                check_out=today_rome() + timedelta(days=3),
            )
        )
        db_session.flush()

        assert service.intervallo_prossimo_sync(
            db_session, feed_pronto.host_id, feed_pronto
        ) == timedelta(minutes=15)

    def test_il_ritmo_stretto_arriva_fino_al_due_at_del_job(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Fino in fondo: non basta che la funzione ritorni 5 minuti, deve
        # finire nel `due_at` della riga in coda. E' il punto in cui l'AC 10
        # smette di essere una funzione e diventa comportamento del poller.
        #
        # L'arrivo vicino lo porta il FEED, non una riga inserita a mano: una
        # Prenotazione che non e' nel corpo scaricato viene giustamente marcata
        # `rimossa_dal_feed` dalla riconciliazione, e smetterebbe di contare.
        # E' il tipo di errore che rende un test verde per la ragione sbagliata
        # — qui l'ha reso rosso, che e' il verso fortunato.
        domani = today_rome() + timedelta(days=1)
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=calendario(
                    vevent(
                        "arrivo-domani@example.com",
                        dal=domani.strftime("%Y%m%d"),
                        al=(domani + timedelta(days=2)).strftime("%Y%m%d"),
                    )
                )
            ),
        )
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        for job in job_periodici(db_session, feed):
            db_session.delete(job)
        db_session.commit()

        esegui_sync_periodico(
            db_session,
            {"feed_id": str(feed.id), "host_id": str(feed.host_id)},
        )
        db_session.commit()

        job = job_periodici(db_session, feed)[0]
        assert job.due_at > utcnow()
        assert job.due_at <= utcnow() + timedelta(minutes=6)


class TestUnFallimentoNonErodeIDati:
    """AC 6 (P0) — il fallimento temporaneo lascia INTATTO ciò che c'è."""

    @pytest.fixture
    def feed_popolato(
        self, db_session: Session, server_feed: ServerFeed, feed_pronto: FeedIcal
    ) -> FeedIcal:
        sincronizza(db_session, feed_pronto, client())
        return feed_pronto

    @pytest.mark.parametrize(
        ("risposta", "categoria"),
        [
            (RispostaPreparata(stato=503), CategoriaErroreSync.ESITO_HTTP_INATTESO),
            (RispostaPreparata(corpo=b""), CategoriaErroreSync.FEED_NON_VALIDO),
            (
                RispostaPreparata(corpo=b"BEGIN:VCALENDAR\r\n", chiudi_a_meta=True),
                CategoriaErroreSync.URL_NON_RAGGIUNGIBILE,
            ),
        ],
    )
    def test_molti_giri_falliti_di_fila_non_erodono_una_prenotazione(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato: FeedIcal,
        risposta: RispostaPreparata,
        categoria: CategoriaErroreSync,
    ) -> None:
        # Il poller gira ogni quindici minuti: un difetto che erode una
        # Prenotazione per giro svuota il calendario entro un giorno, e la
        # differenza col caso on-demand della 2.1 è tutta qui — lì il
        # fallimento è un evento, qui è un regime.
        server_feed.prepara(PERCORSO, risposta)

        for _ in range(4):
            esegui_sync_periodico(
                db_session,
                {
                    "feed_id": str(feed_popolato.id),
                    "host_id": str(feed_popolato.host_id),
                },
            )
            db_session.commit()

        righe = prenotazioni(db_session, feed_popolato)
        assert len(righe) == 2
        assert {riga.stato for riga in righe} == {StatoPrenotazione.ATTIVA}
        assert (
            service.ultimo_run(
                db_session, feed_popolato.host_id, feed_popolato.id
            ).categoria_errore
            is categoria
        )

    def test_dopo_i_fallimenti_il_feed_riprende_senza_perdite(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        for _ in range(3):
            sincronizza(db_session, feed_popolato, client())
        server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))

        run = sincronizza(db_session, feed_popolato, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.prenotazioni_rimosse_dal_feed == 0
        assert len(prenotazioni(db_session, feed_popolato)) == 2


class TestFallimentiConsecutiviEAlert:
    """AC 8 — alert interno alla soglia, e l'azzeramento al primo successo."""

    @pytest.fixture
    def feed_che_fallisce(
        self, db_session: Session, server_feed: ServerFeed, feed_pronto: FeedIcal
    ) -> FeedIcal:
        sincronizza(db_session, feed_pronto, client())
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        return feed_pronto

    def _consecutivi(self, db: Session, feed: FeedIcal) -> int:
        return service.stato_del_feed(db, feed.host_id, feed).fallimenti_consecutivi

    def test_il_contatore_sale_a_ogni_fallimento(
        self, db_session: Session, feed_che_fallisce: FeedIcal
    ) -> None:
        for atteso in (1, 2, 3):
            sincronizza(db_session, feed_che_fallisce, client())
            assert self._consecutivi(db_session, feed_che_fallisce) == atteso

    def test_il_primo_successo_AZZERA_il_contatore(
        self, db_session: Session, server_feed: ServerFeed, feed_che_fallisce: FeedIcal
    ) -> None:
        # È la metà che si dimentica, e per questo il contatore è DERIVATO
        # dalla traccia invece che mantenuto sul Feed: l'azzeramento non è
        # codice che qualcuno deve ricordarsi di scrivere.
        for _ in range(3):
            sincronizza(db_session, feed_che_fallisce, client())
        assert self._consecutivi(db_session, feed_che_fallisce) == 3

        server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))
        sincronizza(db_session, feed_che_fallisce, client())

        assert self._consecutivi(db_session, feed_che_fallisce) == 0

    def test_un_feed_mai_riuscito_conta_tutti_i_suoi_fallimenti(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        for _ in range(2):
            sincronizza(db_session, feed, client())

        assert self._consecutivi(db_session, feed) == 2

    def test_l_alert_scatta_ALLA_soglia_e_non_prima(
        self,
        db_session: Session,
        feed_che_fallisce: FeedIcal,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        soglia = get_settings().feed_sync_fallimenti_per_alert
        with caplog.at_level(logging.ERROR, logger="app.calendario.service"):
            for _ in range(soglia - 1):
                sincronizza(db_session, feed_che_fallisce, client())
            assert self._alert(caplog) == []

            sincronizza(db_session, feed_che_fallisce, client())

        alert = self._alert(caplog)
        assert len(alert) == 1
        assert alert[0].fallimenti_consecutivi == soglia
        assert alert[0].feed_id == str(feed_che_fallisce.id)
        assert alert[0].struttura_id == str(feed_che_fallisce.struttura_id)

    def test_l_alert_non_si_ripete_a_ogni_fallimento_successivo(
        self,
        db_session: Session,
        feed_che_fallisce: FeedIcal,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Un portale giù per un giorno produrrebbe novantasei righe identiche,
        # e un alert che si ripete è un alert che si impara a ignorare.
        soglia = get_settings().feed_sync_fallimenti_per_alert
        with caplog.at_level(logging.ERROR, logger="app.calendario.service"):
            for _ in range(soglia + 3):
                sincronizza(db_session, feed_che_fallisce, client())

        assert len(self._alert(caplog)) == 1

    def test_dopo_un_recupero_un_nuovo_guasto_torna_a_segnalare(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_che_fallisce: FeedIcal,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        soglia = get_settings().feed_sync_fallimenti_per_alert
        with caplog.at_level(logging.ERROR, logger="app.calendario.service"):
            for _ in range(soglia):
                sincronizza(db_session, feed_che_fallisce, client())
            server_feed.prepara(PERCORSO, RispostaPreparata(corpo=DUE_EVENTI))
            sincronizza(db_session, feed_che_fallisce, client())
            server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
            for _ in range(soglia):
                sincronizza(db_session, feed_che_fallisce, client())

        assert len(self._alert(caplog)) == 2

    def test_la_soglia_arriva_dalla_configurazione(
        self,
        db_session: Session,
        feed_che_fallisce: FeedIcal,
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # «N configurabile, mai hardcoded» (AC 8): si prova cambiando N e
        # vedendo cambiare quando scatta.
        monkeypatch.setenv("HOSTPILOT_FEED_SYNC_FALLIMENTI_PER_ALERT", "2")
        get_settings.cache_clear()
        with caplog.at_level(logging.ERROR, logger="app.calendario.service"):
            sincronizza(db_session, feed_che_fallisce, client())
            assert self._alert(caplog) == []
            sincronizza(db_session, feed_che_fallisce, client())

        assert [riga.fallimenti_consecutivi for riga in self._alert(caplog)] == [2]

    def test_l_alert_non_porta_dettagli_tecnici_ne_url(
        self,
        db_session: Session,
        feed_che_fallisce: FeedIcal,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # L'URL del Feed porta il segreto in query (NFR-17): un alert che lo
        # stampasse lo consegnerebbe a chiunque legga i log.
        with caplog.at_level(logging.ERROR, logger="app.calendario.service"):
            for _ in range(get_settings().feed_sync_fallimenti_per_alert):
                sincronizza(db_session, feed_che_fallisce, client())

        alert = self._alert(caplog)[0]
        assert "categoria_errore" in alert.__dict__
        assert not hasattr(alert, "url")
        assert "http" not in alert.getMessage()

    @staticmethod
    def _alert(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
        return [
            riga
            for riga in caplog.records
            if riga.levelno == logging.ERROR
            and riga.getMessage().startswith("alert: feed non sincronizza")
        ]


class TestVeritaTemporaleSottoIlPoller:
    """AC 9 e 11 — il timestamp non avanza sui fallimenti, e «non so» si dice."""

    def test_un_feed_mai_riuscito_non_espone_alcun_orario(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # AC 11 (P0): è il caso in cui la falsa sincronia fa il danno massimo.
        # Il sistema dice «non so» invece di inventare un orario o di tacere.
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        sincronizza(db_session, feed, client())

        stato = service.stato_del_feed(db_session, feed.host_id, feed)

        assert stato.stato is StatoSincronizzazione.FALLITO
        assert stato.ultimo_sync_riuscito_il is None
        assert stato.ultimo_tentativo_il is not None
        assert stato.fallimenti_consecutivi == 1

    def test_una_lunga_serie_di_giri_falliti_non_fa_avanzare_l_orario(
        self, db_session: Session, server_feed: ServerFeed, feed_pronto: FeedIcal
    ) -> None:
        sincronizza(db_session, feed_pronto, client())
        riuscito = service.ultimo_run_riuscito(
            db_session, feed_pronto.host_id, feed_pronto.id
        )
        assert riuscito is not None

        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        for _ in range(5):
            esegui_sync_periodico(
                db_session,
                {
                    "feed_id": str(feed_pronto.id),
                    "host_id": str(feed_pronto.host_id),
                },
            )
            db_session.commit()

        stato = service.stato_del_feed(db_session, feed_pronto.host_id, feed_pronto)
        assert stato.ultimo_sync_riuscito_il == riuscito.concluso_il
        assert stato.ultimo_tentativo_il > riuscito.concluso_il
        assert stato.fallimenti_consecutivi == 5


class TestUnFeedRottoNonBloccaGliAltri:
    """AC 12 — proprietà di REGIME: si osserva solo con più job in tabella."""

    def test_un_feed_permanentemente_rotto_non_ferma_la_coda(
        self, db_session: Session, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara("/buono.ics", RispostaPreparata(corpo=DUE_EVENTI))
        server_feed.prepara("/rotto.ics", RispostaPreparata(stato=500))
        feed = {}
        for nome, percorso in (("buono", "/buono.ics"), ("rotto", "/rotto.ics")):
            host = crea_host(db_session, f"host.{nome}@example.com")
            struttura = crea_struttura(db_session, host.id, f"Appartamento {nome}")
            db_session.commit()
            feed[nome] = collega(
                db_session,
                Contesto(host_id=host.id, struttura_id=struttura.id),
                server_feed.url(percorso),
            )

        for _ in range(4):
            for job in db_session.scalars(
                select(Job).where(Job.status == JobStatus.PENDING)
            ):
                job.due_at = utcnow() - timedelta(seconds=1)
            db_session.commit()
            run_due_jobs(db_session)
            db_session.commit()

        # Il Feed buono ha importato, e continua ad avere un ciclo in coda.
        assert len(prenotazioni(db_session, feed["buono"])) == 2
        assert len(job_periodici(db_session, feed["buono"])) == 1
        # Il Feed rotto NON è un silenzio: ha una traccia di fallimenti e uno
        # stato visibile, e non ha portato con sé la coda.
        assert len(job_periodici(db_session, feed["rotto"])) == 1
        stato = service.stato_del_feed(db_session, feed["rotto"].host_id, feed["rotto"])
        assert stato.stato is StatoSincronizzazione.FALLITO
        assert stato.fallimenti_consecutivi >= 4

    def test_un_handler_che_solleva_esaurisce_i_tentativi_e_resta_VISIBILE(
        self, db_session: Session, feed_pronto: FeedIcal
    ) -> None:
        # L'esaurimento dei tentativi deve essere uno stato leggibile, non un
        # silenzio: `failed` più `last_error`. Senza, un ciclo morto sarebbe
        # indistinguibile da uno che non è ancora scaduto.
        job = job_periodici(db_session, feed_pronto)[0]
        job.max_attempts = 2
        db_session.commit()

        class Esplosivo:
            @staticmethod
            def handler_for(_: str):
                def esplodi(*_args: object) -> None:
                    raise RuntimeError("portale irrecuperabile")

                return esplodi

        for _ in range(job.max_attempts):
            job.due_at = utcnow() - timedelta(seconds=1)
            job.status = JobStatus.PENDING
            db_session.commit()
            run_due_jobs(db_session, Esplosivo())  # type: ignore[arg-type]
            db_session.commit()

        db_session.refresh(job)
        assert job.status is JobStatus.FAILED
        assert job.attempts == job.max_attempts
        assert "portale irrecuperabile" in (job.last_error or "")
        # E la rete di sicurezza lo riprende: il ciclo non resta morto.
        assert bootstrap_sync_periodico(db_session) == 1
