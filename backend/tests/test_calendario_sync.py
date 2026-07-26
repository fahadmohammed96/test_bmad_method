"""Integration del sync dei Feed iCal (Story 2.1) su PostgreSQL reale.

La rete si stub-a **al trasporto**, con un server HTTP su 127.0.0.1
(`tests/server_feed.py`): redirect, `Content-Length`, chiusura anticipata,
timeout e cap di dimensione *sono* il comportamento sotto test, e un mock a
livello di service li cancellerebbe dal mondo — il test finirebbe per
misurare il mock (retrospettiva Epic 1 §3.3).

Nessun dato reale di Ospiti nei fixture (NFR-16).
"""

import gzip
import threading
import time
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import (
    CanaleFeed,
    CategoriaErroreSync,
    EsitoSyncRun,
    FeedIcal,
    Prenotazione,
    StatoPrenotazione,
)
from app.calendario.schemas import StatoSincronizzazione
from app.calendario.trasporto import (
    NOME_THREAD_FETCH,
    ClientFeedHttp,
    EsitoHttpInattesoError,
    TimeoutFeedError,
    UrlNonRaggiungibileError,
)
from app.calendario.uscita_rete import PoliticaUscitaRete, UrlFeedNonValidoError
from app.core.date_range import utcnow
from app.core.jobs import Job, JobStatus
from app.strutture.service import StrutturaNonTrovataError
from tests.calendario import (
    Contesto,
    calendario,
    client,
    collega,
    crea_host,
    crea_struttura,
    fixture_ical,
    politica,
    prenotazioni,
    sincronizza,
    vevent,
)
from tests.server_feed import RispostaPreparata, ServerFeed


def _thread_di_fetch() -> list[threading.Thread]:
    """Thread del trasporto ancora vivi: il presidio sulle perdite."""
    return [
        thread
        for thread in threading.enumerate()
        if thread.name.startswith(NOME_THREAD_FETCH)
    ]


class TestCollegamentoDelFeed:
    """AC 1 e AC 5: accodamento immediato, errore inline sincrono."""

    def test_collegare_un_url_valido_accoda_subito_un_job_di_sync(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        feed = collega(db_session, contesto, "https://feed.example.com/calendario.ics")

        job = db_session.scalars(
            select(Job).where(Job.job_type == "feed_ical.sync_richiesto")
        ).one()
        assert job.payload == {"feed_id": str(feed.id), "host_id": str(feed.host_id)}
        assert job.status is JobStatus.PENDING
        # «Prioritario» = già scaduto: il worker lo prende al primo giro,
        # mentre ogni ciclo periodico ha `due_at` nel futuro.
        assert job.due_at <= utcnow()

    def test_il_job_di_sync_precede_i_cicli_periodici(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        from app.identity.jobs import assicura_purge_periodico

        assicura_purge_periodico(db_session)
        db_session.commit()
        collega(db_session, contesto, "https://feed.example.com/calendario.ics")

        scaduti = db_session.scalars(
            select(Job).where(Job.due_at <= utcnow(), Job.status == JobStatus.PENDING)
        ).all()
        assert [job.job_type for job in scaduti] == ["feed_ical.sync_richiesto"]

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://feed.example.com/c.ics",
            "non-un-url",
            "http://",
        ],
    )
    def test_un_url_non_valido_e_rifiutato_subito_e_senza_rete(
        self, db_session: Session, contesto: Contesto, url: str
    ) -> None:
        with pytest.raises(UrlFeedNonValidoError):
            collega(db_session, contesto, url)
        db_session.rollback()
        assert db_session.scalars(select(FeedIcal)).all() == []
        assert db_session.scalars(select(Job)).all() == []

    def test_non_si_collega_un_feed_alla_struttura_di_un_altro_host(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        altro = crea_host(db_session, "altro.host@example.com")
        db_session.commit()
        with pytest.raises(StrutturaNonTrovataError):
            service.collega_feed(
                db_session,
                altro.id,
                service.DatiFeed(
                    struttura_id=contesto.struttura_id,
                    url="https://feed.example.com/c.ics",
                    canale=CanaleFeed.BOOKING,
                ),
            )


class TestPrimoImport:
    """AC 2, 7, 8, 9: prenotazioni normalizzate, sync_run, tenancy."""

    def test_importa_le_prenotazioni_normalizzate_sulla_struttura_corretta(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.prenotazioni_importate == 2
        righe = prenotazioni(db_session, feed)
        assert [
            (riga.check_in.isoformat(), riga.check_out.isoformat()) for riga in righe
        ] == [
            ("2026-08-10", "2026-08-14"),
            ("2026-08-20", "2026-08-21"),
        ]
        assert {riga.struttura_id for riga in righe} == {contesto.struttura_id}
        assert {riga.host_id for riga in righe} == {contesto.host_id}
        assert {riga.canale for riga in righe} == {CanaleFeed.AIRBNB}
        assert {riga.stato for riga in righe} == {StatoPrenotazione.ATTIVA}

    def test_ogni_run_scrive_un_sync_run_con_esito_e_timestamp(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())

        assert run.iniziato_il <= run.concluso_il
        assert service.ultimo_run(db_session, feed.host_id, feed.id).id == run.id
        assert (
            service.ultimo_run_riuscito(db_session, feed.host_id, feed.id).id == run.id
        )

    def test_verso_l_ota_si_manda_solo_una_get(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        assert [metodo for metodo, _, _ in server_feed.richieste] == ["GET"]

    def test_gli_eventi_malformati_si_contano_e_non_fermano_i_buoni(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("eventi-malformati.ics")),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.eventi_malformati == 4
        assert run.prenotazioni_importate == 1
        assert [riga.ical_uid for riga in prenotazioni(db_session, feed)] == [
            "ffff6666-buono@example.com"
        ]

    def test_una_ricorrenza_entra_come_singola_occorrenza_ed_e_contata(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("semantica-e-durata.ics")),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())

        assert run.eventi_ricorrenti_non_espansi == 1

    def test_status_cancelled_arriva_come_prenotazione_cancellata(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("semantica-e-durata.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        stati = {riga.ical_uid: riga.stato for riga in prenotazioni(db_session, feed)}
        assert stati["7777-cancellato@example.com"] is StatoPrenotazione.CANCELLATA
        assert stati["7777-trasparente@example.com"] is StatoPrenotazione.ATTIVA


class TestIdempotenza:
    """AC 2 e AC 10: la chiave naturale è LA COPPIA `(feed_id, ical_uid)`."""

    def test_rieseguire_il_sync_non_duplica_ne_perde(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)

        primo = sincronizza(db_session, feed, client())
        secondo = sincronizza(db_session, feed, client())
        terzo = sincronizza(db_session, feed, client())

        assert primo.prenotazioni_importate == 2
        assert (secondo.prenotazioni_importate, secondo.prenotazioni_aggiornate) == (
            0,
            2,
        )
        assert terzo.prenotazioni_rimosse_dal_feed == 0
        assert len(prenotazioni(db_session, feed)) == 2

    def test_le_date_cambiate_aggiornano_la_riga_esistente(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        percorso = "/calendario.ics"
        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())

        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260811", al="20260815")
                )
            ),
        )
        run = sincronizza(db_session, feed, client())

        assert run.prenotazioni_aggiornate == 1
        riga = prenotazioni(db_session, feed)[0]
        assert riga.check_in.isoformat() == "2026-08-11"
        assert riga.check_out.isoformat() == "2026-08-15"
        assert len(prenotazioni(db_session, feed)) == 1

    def test_lo_stesso_uid_su_feed_diversi_resta_due_prenotazioni(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # È il test che distingue la chiave giusta da quella che SEMBRA
        # giusta: un UNIQUE sul solo `ical_uid` passerebbe l'AC 2 e
        # romperebbe qui.
        corpo = calendario(
            vevent("condiviso@example.com", dal="20260810", al="20260812")
        )
        primo_url = server_feed.prepara("/airbnb.ics", RispostaPreparata(corpo=corpo))
        secondo_url = server_feed.prepara(
            "/booking.ics", RispostaPreparata(corpo=corpo)
        )

        airbnb = collega(db_session, contesto, primo_url, CanaleFeed.AIRBNB)
        booking = collega(db_session, contesto, secondo_url, CanaleFeed.BOOKING)
        sincronizza(db_session, airbnb, client())
        sincronizza(db_session, booking, client())

        tutte = db_session.scalars(select(Prenotazione)).all()
        assert len(tutte) == 2
        assert {riga.feed_id for riga in tutte} == {airbnb.id, booking.id}

    def test_un_uid_duplicato_nello_stesso_feed_da_una_sola_riga(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("uid-duplicato.ics")),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())

        righe = prenotazioni(db_session, feed)
        assert len(righe) == 1
        # Criterio deterministico e dichiarato: vince l'ULTIMA occorrenza.
        assert righe[0].check_in.isoformat() == "2026-09-01"
        assert (run.prenotazioni_importate, run.prenotazioni_aggiornate) == (1, 1)


class TestScomparsoDalFeed:
    """AC 3: l'import non cancella mai (AD-4, AD-19)."""

    def _due_eventi(self) -> bytes:
        return calendario(
            vevent("resta@example.com", dal="20260810", al="20260812"),
            vevent("sparisce@example.com", dal="20260901", al="20260903"),
        )

    def test_un_evento_scomparso_porta_la_prenotazione_a_rimossa_dal_feed(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        percorso = "/calendario.ics"
        server_feed.prepara(percorso, RispostaPreparata(corpo=self._due_eventi()))
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())

        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("resta@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        run = sincronizza(db_session, feed, client())

        assert run.prenotazioni_rimosse_dal_feed == 1
        stati = {riga.ical_uid: riga.stato for riga in prenotazioni(db_session, feed)}
        # La riga è ancora lì: transizione, non cancellazione.
        assert stati == {
            "resta@example.com": StatoPrenotazione.ATTIVA,
            "sparisce@example.com": StatoPrenotazione.RIMOSSA_DAL_FEED,
        }

    def test_la_transizione_e_idempotente(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        percorso = "/calendario.ics"
        server_feed.prepara(percorso, RispostaPreparata(corpo=self._due_eventi()))
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())
        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("resta@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        sincronizza(db_session, feed, client())
        secondo = sincronizza(db_session, feed, client())

        # Già transizionata: non si ri-conta a ogni giro.
        assert secondo.prenotazioni_rimosse_dal_feed == 0

    def test_un_evento_che_ricompare_non_torna_attivo_da_solo_ma_si_conta(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # La transizione di ritorno è una decisione di prodotto APERTA
        # (test design §4.2-2): qui si sceglie di non risuscitare nulla in
        # silenzio, e di rendere il fatto visibile con un contatore.
        percorso = "/calendario.ics"
        server_feed.prepara(percorso, RispostaPreparata(corpo=self._due_eventi()))
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())
        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("resta@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        sincronizza(db_session, feed, client())

        server_feed.prepara(percorso, RispostaPreparata(corpo=self._due_eventi()))
        run = sincronizza(db_session, feed, client())

        assert run.prenotazioni_ricomparse == 1
        stati = {riga.ical_uid: riga.stato for riga in prenotazioni(db_session, feed)}
        assert stati["sparisce@example.com"] is StatoPrenotazione.RIMOSSA_DAL_FEED

    def test_un_evento_malformato_ma_presente_non_conta_come_scomparso(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Sottigliezza della stessa famiglia di E2-G3: l'uid è NEL feed, solo
        # l'evento non si normalizza. Escluderlo dagli uid presenti
        # marcherebbe `rimossa_dal_feed` una Prenotazione viva.
        percorso = "/calendario.ics"
        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())

        malformato = (
            "BEGIN:VEVENT\r\nUID:uid-1@example.com\r\n"
            "DTSTART;VALUE=DATE:20260810\r\nEND:VEVENT\r\n"
        )
        server_feed.prepara(percorso, RispostaPreparata(corpo=calendario(malformato)))
        run = sincronizza(db_session, feed, client())

        assert run.eventi_malformati == 1
        assert run.prenotazioni_rimosse_dal_feed == 0
        assert prenotazioni(db_session, feed)[0].stato is StatoPrenotazione.ATTIVA


class TestGuardiaDelRepository:
    """La difesa in profondita' va pinnata, o il prossimo giro la cancella.

    La guardia sul caso vuoto in `marca_rimosse_dal_feed` non era coperta da
    nessun test: il service cortocircuita prima, quindi cancellarla lasciava
    la suite verde. Un passaggio di pulizia («ramo irraggiungibile») l'avrebbe
    tolta in buona fede, e il P0 sarebbe tornato a dipendere da un solo
    livello.
    """

    def test_con_uid_presenti_vuoto_non_marca_nulla(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        from app.calendario.repository import PrenotazioneRepository

        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                    vevent("uid-2@example.com", dal="20260901", al="20260903"),
                )
            ),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        # Chiamata DIRETTA al repository, saltando la decisione del service.
        rimosse = PrenotazioneRepository(db_session).marca_rimosse_dal_feed(
            feed.host_id, feed_id=feed.id, uid_presenti=[]
        )
        db_session.commit()

        assert rimosse == 0
        assert {riga.stato for riga in prenotazioni(db_session, feed)} == {
            StatoPrenotazione.ATTIVA
        }

    def test_con_un_uid_presente_marca_solo_gli_altri(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # L'altra metà: la guardia non deve inibire il comportamento normale.
        from app.calendario.repository import PrenotazioneRepository

        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                    vevent("uid-2@example.com", dal="20260901", al="20260903"),
                )
            ),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        rimosse = PrenotazioneRepository(db_session).marca_rimosse_dal_feed(
            feed.host_id, feed_id=feed.id, uid_presenti=["uid-1@example.com"]
        )
        db_session.commit()

        assert rimosse == 1
        stati = {riga.ical_uid: riga.stato for riga in prenotazioni(db_session, feed)}
        assert stati["uid-1@example.com"] is StatoPrenotazione.ATTIVA
        assert stati["uid-2@example.com"] is StatoPrenotazione.RIMOSSA_DAL_FEED


class TestScomparsoNonERicevuto:
    """AC 4 — E2-G3, il rischio peggiore dell'Epic (R2-C).

    `rimossa_dal_feed` si applica SOLO dopo un parse completo e validato.
    Ogni riga di questa classe è un modo in cui il trasporto può mentire: se
    una passasse, un errore di rete svuoterebbe il calendario e i Conflitti
    aperti `decadrebbero` — senza alcun errore visibile.
    """

    @pytest.fixture
    def feed_popolato(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> FeedIcal:
        percorso = "/calendario.ics"
        server_feed.prepara(
            percorso,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                    vevent("uid-2@example.com", dal="20260901", al="20260903"),
                )
            ),
        )
        feed = collega(db_session, contesto, server_feed.url(percorso))
        sincronizza(db_session, feed, client())
        return feed

    def _assert_dati_intatti(self, db: Session, feed: FeedIcal) -> None:
        righe = prenotazioni(db, feed)
        assert len(righe) == 2
        assert {riga.stato for riga in righe} == {StatoPrenotazione.ATTIVA}

    @pytest.mark.parametrize(
        ("risposta", "categoria"),
        [
            (
                RispostaPreparata(corpo=fixture_ical("troncato-a-meta-vevent.ics")),
                CategoriaErroreSync.FEED_NON_VALIDO,
            ),
            (RispostaPreparata(corpo=b""), CategoriaErroreSync.FEED_NON_VALIDO),
            (
                RispostaPreparata(corpo=b"<html>Servizio non disponibile</html>"),
                CategoriaErroreSync.FEED_NON_VALIDO,
            ),
            (
                RispostaPreparata(corpo=fixture_ical("solo-intestazione.ics")),
                CategoriaErroreSync.FEED_SENZA_EVENTI,
            ),
            (RispostaPreparata(stato=304), CategoriaErroreSync.ESITO_HTTP_INATTESO),
            (RispostaPreparata(stato=500), CategoriaErroreSync.ESITO_HTTP_INATTESO),
            (RispostaPreparata(stato=404), CategoriaErroreSync.ESITO_HTTP_INATTESO),
            (
                RispostaPreparata(
                    corpo=b"BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nUID:x\r\n",
                    chiudi_a_meta=True,
                ),
                CategoriaErroreSync.URL_NON_RAGGIUNGIBILE,
            ),
            # Nona forma. Un VCALENDAR chiuso i cui VEVENT non portano `UID`
            # supera sia il parser sia la guardia «nessun evento»: gli eventi
            # ci sono, solo non sono identificabili. Senza il presidio, la
            # riconciliazione parte con `uid_presenti` vuoto e la UPDATE
            # degenera in «tutte» — e il run risulta RIUSCITO, quindi la UI
            # non segnala nulla e i Conflitti decadono in silenzio.
            (
                RispostaPreparata(corpo=fixture_ical("senza-uid.ics")),
                CategoriaErroreSync.FEED_SENZA_EVENTI,
            ),
            # Stessa porta, forma più sottile: l'`UID` c'è ma è vuoto, e
            # `Vevent.uid` ritorna `None` in entrambi i casi.
            (
                RispostaPreparata(
                    corpo=(
                        b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
                        b"UID:   \r\nDTSTART;VALUE=DATE:20260810\r\n"
                        b"DTEND;VALUE=DATE:20260812\r\nSUMMARY:Reserved\r\n"
                        b"END:VEVENT\r\nEND:VCALENDAR\r\n"
                    )
                ),
                CategoriaErroreSync.FEED_SENZA_EVENTI,
            ),
        ],
    )
    def test_una_risposta_che_non_e_un_feed_completo_non_transiziona_nulla(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato: FeedIcal,
        risposta: RispostaPreparata,
        categoria: CategoriaErroreSync,
    ) -> None:
        server_feed.prepara("/calendario.ics", risposta)

        run = sincronizza(db_session, feed_popolato, client())

        # Prima l'invariante di DATO, poi la contabilità: se il primo cade è
        # una doppia prenotazione ospitata, se cade il secondo è un'etichetta.
        assert run.prenotazioni_rimosse_dal_feed == 0
        self._assert_dati_intatti(db_session, feed_popolato)
        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is categoria

    def test_senza_uid_utilizzabili_la_riconciliazione_non_parte_affatto(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        # La forma stretta del difetto: gli eventi ci SONO (quindi la guardia
        # «nessun evento» non basta), ma nessuno è identificabile.
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("senza-uid.ics")),
        )

        run = sincronizza(db_session, feed_popolato, client())

        assert run.prenotazioni_rimosse_dal_feed == 0
        self._assert_dati_intatti(db_session, feed_popolato)
        # E soprattutto: NON riuscito. Con esito riuscito la UI non
        # segnalerebbe niente e i Conflitti decadrebbero in silenzio.
        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.FEED_SENZA_EVENTI

    def test_un_solo_uid_valido_fra_molti_senza_uid_riconcilia_solo_quello(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        # Il confine opposto: basta UN uid utilizzabile perché il feed sia
        # riconciliabile, e allora la transizione degli scomparsi è corretta
        # e dovuta. La guardia non deve diventare un'inibizione generale.
        senza_uid = (
            "BEGIN:VEVENT\r\nDTSTART;VALUE=DATE:20260701\r\n"
            "DTEND;VALUE=DATE:20260702\r\nSUMMARY:Reserved\r\nEND:VEVENT\r\n"
        )
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    senza_uid,
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                )
            ),
        )

        run = sincronizza(db_session, feed_popolato, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.eventi_malformati == 1
        # `uid-2` è davvero scomparso dal feed: questa transizione è giusta.
        assert run.prenotazioni_rimosse_dal_feed == 1
        stati = {
            riga.ical_uid: riga.stato
            for riga in prenotazioni(db_session, feed_popolato)
        }
        assert stati["uid-1@example.com"] is StatoPrenotazione.ATTIVA
        assert stati["uid-2@example.com"] is StatoPrenotazione.RIMOSSA_DAL_FEED

    def test_un_run_fallito_non_fa_avanzare_l_ultimo_sync_riuscito(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        riuscito = service.ultimo_run_riuscito(
            db_session, feed_popolato.host_id, feed_popolato.id
        )
        assert riuscito is not None

        server_feed.prepara("/calendario.ics", RispostaPreparata(stato=500))
        sincronizza(db_session, feed_popolato, client())

        # NFR-2: «dati aggiornati alle HH:MM» non avanza su un run fallito.
        dopo = service.ultimo_run_riuscito(
            db_session, feed_popolato.host_id, feed_popolato.id
        )
        assert dopo.id == riuscito.id
        assert (
            service.ultimo_run(
                db_session, feed_popolato.host_id, feed_popolato.id
            ).esito
            is EsitoSyncRun.FALLITO
        )

    def test_il_feed_torna_valido_e_l_import_riprende(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        server_feed.prepara("/calendario.ics", RispostaPreparata(stato=503))
        sincronizza(db_session, feed_popolato, client())
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                    vevent("uid-2@example.com", dal="20260901", al="20260903"),
                )
            ),
        )
        run = sincronizza(db_session, feed_popolato, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.prenotazioni_rimosse_dal_feed == 0


class TestOgniRunLasciaTraccia:
    """AC 7 e AC 5: un VEVENT ostile non può cancellare il `sync_run`.

    Il loop di normalizzazione gira dentro il SAVEPOINT per item del worker
    (G-1): un'eccezione che sfugge annulla la riga `sync_run` insieme
    all'errore, il Feed torna a «mai sincronizzato» senza categoria e il
    polling del frontend si spegne. Il contenuto è di terze parti, quindi
    l'insieme dei modi in cui può essere illeggibile non è enumerabile: qui si
    provano i due noti e si pretende che la classe sia chiusa.
    """

    @pytest.fixture
    def feed_popolato(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> FeedIcal:
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        feed = collega(db_session, contesto, server_feed.url("/calendario.ics"))
        sincronizza(db_session, feed, client())
        return feed

    @pytest.mark.parametrize(
        ("descrizione", "corpo"),
        [
            (
                # NON e' `timedelta` a esplodere: `timedelta.max.days` e'
                # 999 999 999, quindi 8 cifre ci stanno comodamente. Salta la
                # SOMMA con la data (`_giorno_locale(inizio) + delta`), perche'
                # `date.max` e' l'anno 9999.
                "durata che sfonda date.max nella somma",
                calendario(
                    "BEGIN:VEVENT\r\nUID:ostile-durata@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\nDURATION:P99999999D\r\n"
                    "SUMMARY:Reserved\r\nEND:VEVENT\r\n"
                ),
            ),
            (
                # Questo si', invece: dieci cifre sfondano `timedelta` prima
                # di arrivare alla somma. Percorso DIVERSO dai due sopra —
                # senza questo caso la tesi «la classe e' chiusa» poggiava su
                # un solo punto di rottura.
                "durata oltre i limiti di timedelta",
                calendario(
                    "BEGIN:VEVENT\r\nUID:ostile-timedelta@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\nDURATION:P9999999999D\r\n"
                    "SUMMARY:Reserved\r\nEND:VEVENT\r\n"
                ),
            ),
            (
                "uid oltre la lunghezza della colonna",
                calendario(
                    "BEGIN:VEVENT\r\nUID:" + "u" * 600 + "@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\n"
                    "DTEND;VALUE=DATE:20260812\r\nSUMMARY:Reserved\r\n"
                    "END:VEVENT\r\n"
                ),
            ),
            (
                # Stessa riga, unita' diversa: anche questo e' un overflow di
                # `date`, non di `timedelta`.
                "settimane che sfondano date.max nella somma",
                calendario(
                    "BEGIN:VEVENT\r\nUID:ostile-settimane@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\nDURATION:P99999999W\r\n"
                    "SUMMARY:Reserved\r\nEND:VEVENT\r\n"
                ),
            ),
        ],
    )
    def test_un_vevent_ostile_e_malformato_e_il_run_scrive_comunque(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato: FeedIcal,
        descrizione: str,
        corpo: bytes,
    ) -> None:
        # Il feed contiene ANCHE l'evento buono, così l'uid resta presente e
        # la Prenotazione viva non viene toccata.
        completo = corpo.replace(
            b"END:VCALENDAR\r\n",
            vevent("uid-1@example.com", dal="20260810", al="20260812").encode()
            + b"END:VCALENDAR\r\n",
        )
        server_feed.prepara("/calendario.ics", RispostaPreparata(corpo=completo))

        run = sincronizza(db_session, feed_popolato, client())

        # Il `sync_run` ESISTE: è la condizione perché l'Host veda qualcosa.
        assert (
            service.ultimo_run(db_session, feed_popolato.host_id, feed_popolato.id)
            is not None
        )
        assert run.eventi_malformati == 1, descrizione
        assert run.esito is EsitoSyncRun.RIUSCITO
        # L'uid dell'evento ostile è comunque NEL feed: nulla è «scomparso».
        assert run.prenotazioni_rimosse_dal_feed == 0
        assert (
            prenotazioni(db_session, feed_popolato)[0].stato is StatoPrenotazione.ATTIVA
        )

    def test_il_feed_non_torna_mai_sincronizzato_dopo_un_vevent_ostile(
        self, db_session: Session, server_feed: ServerFeed, feed_popolato: FeedIcal
    ) -> None:
        # È il sintomo che l'Host vedrebbe: uno stato che regredisce e un
        # polling che si spegne senza dire perché.
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    "BEGIN:VEVENT\r\nUID:ostile@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\nDURATION:P99999999D\r\n"
                    "SUMMARY:Reserved\r\nEND:VEVENT\r\n",
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                )
            ),
        )

        sincronizza(db_session, feed_popolato, client())

        stato = service.stato_del_feed(
            db_session,
            feed_popolato.host_id,
            service.leggi_feed(db_session, feed_popolato.host_id, feed_popolato.id),
        )
        assert stato.stato is not StatoSincronizzazione.MAI_SINCRONIZZATO
        assert stato.ultimo_tentativo_il is not None

    def test_la_lunghezza_massima_dell_uid_e_quella_della_colonna(self) -> None:
        # Il presidio non deve poter divergere dallo schema: se la colonna
        # cambiasse, il troncamento a monte diventerebbe sbagliato in silenzio.
        from app.calendario.models import Prenotazione as ModelloPrenotazione
        from app.calendario.normalizzazione import LUNGHEZZA_MASSIMA_ICAL_UID

        assert (
            LUNGHEZZA_MASSIMA_ICAL_UID
            == ModelloPrenotazione.__table__.c.ical_uid.type.length
        )


class TestPoliticaDiUscitaDiRete:
    """AC 6 — NFR-17 al livello del trasporto."""

    def _feed_con_url(self, db: Session, contesto: Contesto, url: str) -> FeedIcal:
        return collega(db, contesto, url)

    def test_un_host_che_risolve_su_rete_privata_e_url_non_raggiungibile(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        feed = self._feed_con_url(
            db_session, contesto, "https://feed.example.com/calendario.ics"
        )
        trasporto = ClientFeedHttp(
            politica(reti_consentite=()),
            risolutore=lambda host: ["10.1.2.3"],
        )

        run = sincronizza(db_session, feed, trasporto)

        # Stessa categoria di una connessione fallita: l'errore non rivela
        # l'esito della risoluzione (NFR-17).
        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.URL_NON_RAGGIUNGIBILE

    def test_un_redirect_verso_i_metadati_d_istanza_e_rifiutato_dopo_il_redirect(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il primo hop è lecito; è il SECONDO che punta alla rete interna.
        # Una validazione fatta solo sull'URL iniziale non lo vedrebbe.
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                stato=302,
                intestazioni={"Location": "http://169.254.169.254/latest/meta-data/"},
            ),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client())

        assert run.categoria_errore is CategoriaErroreSync.URL_NON_RAGGIUNGIBILE
        # Il secondo hop non è mai partito.
        assert len(server_feed.richieste) == 1

    def test_un_redirect_lecito_viene_seguito(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(
            "/vero.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(stato=302, intestazioni={"Location": "/vero.ics"}),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.prenotazioni_importate == 1
        assert [percorso for _, percorso, _ in server_feed.richieste] == [
            "/calendario.ics",
            "/vero.ics",
        ]

    def test_una_catena_di_redirect_troppo_lunga_si_ferma(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(
            "/uno.ics",
            RispostaPreparata(stato=302, intestazioni={"Location": "/due.ics"}),
        )
        server_feed.prepara(
            "/due.ics",
            RispostaPreparata(stato=302, intestazioni={"Location": "/tre.ics"}),
        )
        server_feed.prepara(
            "/tre.ics",
            RispostaPreparata(stato=302, intestazioni={"Location": "/uno.ics"}),
        )
        feed = collega(db_session, contesto, server_feed.url("/uno.ics"))

        run = sincronizza(db_session, feed, client(max_redirect=1))

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.URL_NON_RAGGIUNGIBILE
        assert len(server_feed.richieste) == 2

    def test_una_risposta_oltre_il_cap_di_dimensione_chiude_e_fallisce(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        gonfio = calendario(
            vevent(
                "uid-1@example.com",
                dal="20260810",
                al="20260812",
                extra="DESCRIPTION:" + "x" * 4000 + "\r\n",
            )
        )
        url = server_feed.prepara("/calendario.ics", RispostaPreparata(corpo=gonfio))
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client(cap=500))

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.RISPOSTA_TROPPO_GRANDE
        assert prenotazioni(db_session, feed) == []

    def test_un_content_length_oltre_il_cap_si_rifiuta_senza_scaricare(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Un feed che si DICHIARA da 2 GB non merita il primo byte.
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n",
                chiudi_a_meta=True,
            ),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client(cap=40))

        assert run.categoria_errore is CategoriaErroreSync.RISPOSTA_TROPPO_GRANDE

    def test_un_portale_che_non_risponde_fallisce_sul_timeout_di_lettura(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il timeout è il MECCANISMO sotto test, non un'attesa di comodo: la
        # soglia è di configurazione e qui si tara a 200 ms.
        url = server_feed.prepara(
            "/calendario.ics", RispostaPreparata(non_rispondere=True)
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client(lettura=0.2))

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT

    def test_la_connessione_va_all_indirizzo_gia_validato_non_a_una_nuova_dns(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Pinning (DNS rebinding). Il risolutore viene chiamato UNA volta per
        # hop e il suo esito è quello a cui si connette: se il secondo lookup
        # fosse indipendente, un DNS che cambia risposta fra validazione e
        # connessione porterebbe il fetch dove vuole.
        porta = int(server_feed.url("/x").rsplit(":", 1)[1].split("/")[0])
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                )
            ),
        )
        chiamate: list[str] = []

        def risolutore(host: str) -> list[str]:
            chiamate.append(host)
            return ["127.0.0.1"]

        feed = collega(
            db_session, contesto, f"http://feed.example.com:{porta}/calendario.ics"
        )
        trasporto = ClientFeedHttp(politica(), risolutore=risolutore)

        run = sincronizza(db_session, feed, trasporto)

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert chiamate == ["feed.example.com"]
        # L'identità del server resta quella vera: `Host` è il nome, non l'IP.
        _, _, intestazioni = server_feed.richieste[0]
        assert intestazioni["Host"] == f"feed.example.com:{porta}"

    @pytest.mark.parametrize(
        ("origine", "posizione", "ammesso"),
        [
            ("https://feed.example.com/c.ics", "http://feed.example.com/c.ics", False),
            ("https://feed.example.com/c.ics", "/relativo.ics", True),
            (
                "https://feed.example.com/c.ics",
                "https://altro.example.com/c.ics",
                True,
            ),
            # Salire è lecito, scendere no. E `http → http` non è un
            # declassamento: `http` è ammesso in assoluto.
            ("http://feed.example.com/c.ics", "https://feed.example.com/c.ics", True),
            ("http://feed.example.com/c.ics", "http://altro.example.com/c.ics", True),
        ],
    )
    def test_il_calcolo_del_prossimo_hop_vieta_il_declassamento(
        self, origine: str, posizione: str, ammesso: bool
    ) -> None:
        # Il controllo vive DENTRO il calcolo del prossimo hop, non come riga
        # adiacente nel ciclo dei redirect: là era una riga cancellabile senza
        # rompere nulla. Ora il prossimo hop non si calcola senza passare dal
        # controllo, e cancellare il calcolo fa cadere i test dei redirect
        # (`una_catena_di_redirect_troppo_lunga`, `un_redirect_lecito`).
        risposta = httpx.Response(302, headers={"location": posizione})
        if ammesso:
            assert ClientFeedHttp._prossimo_hop(origine, risposta)
        else:
            with pytest.raises(UrlNonRaggiungibileError):
                ClientFeedHttp._prossimo_hop(origine, risposta)

    def test_un_redirect_senza_location_e_un_esito_http_inatteso(self) -> None:
        with pytest.raises(EsitoHttpInattesoError):
            ClientFeedHttp._prossimo_hop(
                "https://feed.example.com/c.ics", httpx.Response(302)
            )

    @pytest.mark.parametrize(
        ("url", "atteso_pinnato", "atteso_host"),
        [
            (
                "https://feed.example.com/c.ics",
                "https://93.184.216.34/c.ics",
                "feed.example.com",
            ),
            (
                "https://feed.example.com:8443/c.ics?s=x",
                "https://93.184.216.34:8443/c.ics?s=x",
                "feed.example.com:8443",
            ),
            # REGRESSIONE del batch precedente: sostituire l'intero netloc
            # cancellava lo userinfo, quindi httpx non derivava piu' il
            # BasicAuth e un Feed credenziato prendeva 401 ->
            # ESITO_HTTP_INATTESO. E' una forma che questo codice supporta
            # esplicitamente (`url_redatto` ha un ramo dedicato).
            (
                "https://utente:pw@feed.example.com/c.ics",
                "https://utente:pw@93.184.216.34/c.ics",
                "feed.example.com",
            ),
            (
                "https://solo-utente@feed.example.com/c.ics",
                "https://solo-utente@93.184.216.34/c.ics",
                "feed.example.com",
            ),
        ],
    )
    def test_il_pinning_conserva_userinfo_porta_e_query(
        self, url: str, atteso_pinnato: str, atteso_host: str
    ) -> None:
        pinnato, intestazioni, estensioni = ClientFeedHttp._richiesta_pinnata(
            url, ("93.184.216.34",)
        )
        assert pinnato == atteso_pinnato
        # `Host` senza userinfo: e' l'identita' del server, non una credenziale.
        assert intestazioni["Host"] == atteso_host
        assert estensioni["sni_hostname"] == "feed.example.com"

    @pytest.mark.parametrize(
        ("url", "atteso_pinnato", "atteso_host"),
        [
            (
                "https://[2001:db8::1]/c.ics",
                "https://[2606:2800:220::1]/c.ics",
                "[2001:db8::1]",
            ),
            (
                "https://[2001:db8::1]:8443/c.ics",
                "https://[2606:2800:220::1]:8443/c.ics",
                "[2001:db8::1]:8443",
            ),
        ],
    )
    def test_il_pinning_mette_le_quadre_a_un_ipv6_anche_nell_host(
        self, url: str, atteso_pinnato: str, atteso_host: str
    ) -> None:
        # `parti.hostname` restituisce l'IPv6 SENZA parentesi: usarlo tale e
        # quale produceva `Host: 2001:db8::1`, che RFC 9110 vuole fra quadre,
        # e con la porta diventava `2001:db8::1:8443` — impossibile da parsare.
        pinnato, intestazioni, _ = ClientFeedHttp._richiesta_pinnata(
            url, ("2606:2800:220::1",)
        )
        assert pinnato == atteso_pinnato
        assert intestazioni["Host"] == atteso_host

    def test_un_feed_credenziato_manda_davvero_il_basic_auth(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # La regressione dello userinfo era pinnata su un'uguaglianza di
        # stringa sul metodo privato. Questa è la PROPRIETÀ che la rendeva una
        # regressione: httpx deriva il BasicAuth dallo userinfo dell'URL, e se
        # il pinning lo cancella il portale risponde 401.
        import base64

        porta = int(server_feed.url("/x").rsplit(":", 1)[1].split("/")[0])
        server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(
            db_session,
            contesto,
            f"http://utente:segreta@feed.example.com:{porta}/calendario.ics",
        )
        trasporto = ClientFeedHttp(politica(), risolutore=lambda host: ["127.0.0.1"])

        run = sincronizza(db_session, feed, trasporto)

        assert run.esito is EsitoSyncRun.RIUSCITO
        _, _, intestazioni = server_feed.richieste[0]
        atteso = base64.b64encode(b"utente:segreta").decode()
        assert intestazioni["Authorization"] == f"Basic {atteso}"

    def test_i_proxy_dell_ambiente_non_vengono_ereditati(
        self,
        db_session: Session,
        contesto: Contesto,
        server_feed: ServerFeed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # `trust_env=False` verificato sul COMPORTAMENTO, non per ispezione:
        # con l'ambiente onorato httpx instraderebbe la richiesta al proxy
        # (che non esiste) e il fetch fallirebbe. Un proxy nell'ambiente del
        # worker azzererebbe l'intera denylist, perché il nome lo
        # risolverebbe il proxy.
        for variabile in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy"):
            monkeypatch.setenv(variabile, "http://127.0.0.1:9/")
        # E si AZZERANO le esclusioni: con `no_proxy=*` o
        # `NO_PROXY=localhost,127.0.0.1` — comuni nelle immagini CI e sulle
        # macchine aziendali — httpx ripristina il transport diretto per il
        # loopback, e il mutante senza `trust_env=False` sopravvive.
        for esclusione in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(esclusione, raising=False)
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.prenotazioni_importate == 2

    def test_si_chiede_di_non_comprimere_la_risposta(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        _, _, intestazioni = server_feed.richieste[0]
        assert intestazioni["Accept-Encoding"] == "identity"

    def test_una_risposta_compressa_e_rifiutata_anche_se_l_abbiamo_vietata(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # `Accept-Encoding` è una richiesta, non una garanzia: `iter_bytes()`
        # decodifica in base al `Content-Encoding` della RISPOSTA. Un portale
        # ostile risponde gzip con un `Content-Length` piccolo che passa il
        # pre-check, e il corpo si espande di ordini di grandezza prima che il
        # cap sui byte decodificati se ne accorga.
        gonfio = gzip.compress(b"A" * 4_000_000)
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=gonfio, intestazioni={"Content-Encoding": "gzip"}),
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client(cap=1_000_000))

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.RISPOSTA_TROPPO_GRANDE
        assert prenotazioni(db_session, feed) == []

    def test_l_azione_abbandonata_gira_in_un_thread_daemon_e_viene_chiusa(
        self,
    ) -> None:
        """Presidio DETERMINISTICO sul meccanismo di abbandono.

        Il test di integrazione qui sotto verifica l'invariante end-to-end (a
        fetch concluso non restano thread), ma non può garantire che il thread
        sia ancora vivo nell'istante in cui lo si ispeziona: la chiusura è
        veloce e l'asserzione sul `daemon` diventerebbe vacua per una corsa.
        Qui l'azione blocca su un `Event` che il test controlla, quindi il
        thread è vivo con certezza quando si guardano le due proprietà.
        """
        trasporto = ClientFeedHttp(politica())
        blocco = threading.Event()
        chiusure: list[str] = []
        try:
            with pytest.raises(TimeoutFeedError):
                trasporto._entro_la_scadenza(
                    lambda: blocco.wait(30),
                    time.monotonic() + 0.2,
                    chiudi=lambda: chiusure.append("chiuso"),
                )

            superstiti = _thread_di_fetch()
            assert superstiti, "il thread deve essere ancora vivo: è il caso da coprire"
            # DAEMON: un thread non-daemon abbandonato blocca l'uscita
            # dell'interprete, quindi un SIGTERM al worker resta appeso fino
            # al SIGKILL — che ammazza il job in volo.
            for superstite in superstiti:
                assert superstite.daemon, f"{superstite.name} non è daemon"
            # E la chiusura è invocata sul percorso di abbandono: è ciò che
            # sgancia la connessione e fa uscire il thread.
            assert chiusure == ["chiuso"]
        finally:
            blocco.set()
        for superstite in superstiti:
            superstite.join(5)
        assert _thread_di_fetch() == []

    def test_un_fetch_abbandonato_non_lascia_thread_ne_connessioni(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # È la proprietà su cui poggia tutto il meccanismo di scadenza, e non
        # aveva presidio: i due test di drip asseriscono che il WORKER è
        # libero, e restano verdi con thread e socket persi per giorni.
        #
        # Perché conta: `collega_feed` accoda un sync a ogni POST, senza tetto
        # sul numero di Feed per Host. N feed ostili = N thread + N fd, e col
        # poller della 2.2 diventa una perdita per ciclo di polling — a 15
        # minuti di cadenza un solo feed sostiene ~1100 thread in stato
        # stazionario.
        url = server_feed.prepara(
            "/calendario.ics", RispostaPreparata(sgocciola_intestazioni_secondi=0.05)
        )
        feed = collega(db_session, contesto, url)

        run = sincronizza(db_session, feed, client(lettura=10.0, deadline=0.4))
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT

        # Il thread abbandonato deve uscire da solo e in fretta: il client
        # viene chiuso, quindi la read successiva solleva. Senza chiusura
        # resterebbe fino a `MAX_INCOMPLETE_EVENT_SIZE` di httpcore (100 KiB ×
        # il timeout di lettura ≈ 284 ore) — e su una costante privata, non un
        # contratto. `daemon` e invocazione della chiusura sono verificati in
        # modo deterministico dal test qui sopra.
        scadenza = time.monotonic() + 5.0
        while time.monotonic() < scadenza and _thread_di_fetch():
            time.sleep(0.05)
        assert _thread_di_fetch() == [], (
            "thread di fetch superstiti dopo l'abbandono: la connessione non "
            "è stata rilasciata"
        )

    def test_un_portale_che_sgocciola_le_INTESTAZIONI_si_ferma_sulla_deadline(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # La fase di TESTA non passa da `iter_bytes`: nessun checkpoint
        # applicativo la vede. Un byte di intestazione ogni pausa sta dentro il
        # timeout di lettura (che si azzera a ogni read) e l'unico tetto
        # aggregato sarebbe `MAX_INCOMPLETE_EVENT_SIZE` di h11, 100 KiB —
        # cioè 102 400 read, ciascuna dentro il timeout. Un insieme di
        # controlli non limita il tempo che passa FRA due controlli: serve un
        # bound che viva sulla socket.
        url = server_feed.prepara(
            "/calendario.ics", RispostaPreparata(sgocciola_intestazioni_secondi=0.05)
        )
        feed = collega(db_session, contesto, url)

        inizio = time.monotonic()
        run = sincronizza(db_session, feed, client(lettura=10.0, deadline=0.6))
        trascorso = time.monotonic() - inizio

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT
        # Sotto il timeout di lettura (10s): se il bound fosse solo
        # per-operazione, questo test non finirebbe prima di ore.
        assert trascorso < 3.0

    def test_un_portale_che_sgocciola_si_ferma_sulla_deadline_complessiva(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # `httpx.Timeout` è solo PER-OPERAZIONE: un byte ogni frazione di
        # secondo non fa scattare nulla, e ai valori di produzione un byte
        # ogni 9 secondi tiene la connessione per mesi. `core/worker.py` è un
        # ciclo sequenziale in-process: la connessione appesa ferma il worker
        # di TUTTI i tenant, non solo quello dell'attaccante. L'AC dice
        # «senza saturare il worker», quindi serve una deadline sull'intero
        # fetch.
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=fixture_ical("airbnb-date-only.ics"), sgocciola_secondi=0.12
            ),
        )
        feed = collega(db_session, contesto, url)

        inizio = time.monotonic()
        # `lettura` MOLTO più alto del margine dell'assert: se coincidessero,
        # l'unico modo in cui il test può dare il colore sbagliato — fermarsi
        # sul timeout di lettura invece che sulla deadline, indistinguibili
        # entrambi come TIMEOUT — cadrebbe esattamente sul confine.
        run = sincronizza(db_session, feed, client(lettura=10.0, deadline=0.6))
        trascorso = time.monotonic() - inizio

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT
        # La deadline deve MORDERE: senza di essa il corpo (oltre 400 byte a
        # 0,12s l'uno) impiegherebbe ~50 secondi, e con il solo timeout di
        # lettura non si fermerebbe mai.
        assert trascorso < 3.0

    def test_la_deadline_non_si_moltiplica_per_i_redirect(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Ogni hop consuma una FRAZIONE del budget: tre ritardi da 0,5s
        # contro una scadenza di 1,2s. Con un budget PER HOP passerebbero
        # tutti e tre (0,5 < 1,2) e il fetch RIUSCIREBBE; con il budget
        # dell'intero fetch no.
        #
        # Senza i ritardi il test non discriminava: bastava che l'ultimo hop
        # sfondasse il proprio budget per restare TIMEOUT anche spostando il
        # calcolo della scadenza dentro il ciclo.
        server_feed.prepara(
            "/uno.ics",
            RispostaPreparata(
                stato=302, intestazioni={"Location": "/due.ics"}, ritardo_secondi=0.5
            ),
        )
        server_feed.prepara(
            "/due.ics",
            RispostaPreparata(
                stato=302, intestazioni={"Location": "/tre.ics"}, ritardo_secondi=0.5
            ),
        )
        server_feed.prepara(
            "/tre.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                ),
                ritardo_secondi=0.5,
            ),
        )
        feed = collega(db_session, contesto, server_feed.url("/uno.ics"))

        # Scala doppia rispetto al primo tentativo: la discriminazione
        # per-hop/totale è identica (ogni ritardo è metà del budget), ma lo
        # slack passa da ~100ms a ~700ms. Serve perché ogni hop costruisce ora
        # un `SSLContext` nuovo (~37ms) e su un runner carico il fetch poteva
        # morire prima che il secondo hop partisse.
        run = sincronizza(
            db_session, feed, client(lettura=10.0, deadline=1.2, max_redirect=3)
        )

        # La proprietà è l'ESITO, non quanti hop sono partiti: il terzo hop
        # può legittimamente iniziare (0,5 + 0,5 < 1,2) e scadere durante.
        # Con un budget PER HOP, invece, tutti e tre completerebbero — ogni
        # ritardo è 0,5 contro 1,2 — e il fetch RIUSCIREBBE. È quella la
        # differenza che questo test misura.
        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT
        assert prenotazioni(db_session, feed) == []
        # E la catena è stata davvero percorsa: non è morta al primo hop per
        # un motivo diverso dal budget.
        assert len(server_feed.richieste) >= 2

    def test_la_deadline_arriva_dalla_configurazione(self) -> None:
        from app.core.config import Settings

        politica_configurata = PoliticaUscitaRete.da_configurazione(
            Settings(feed_deadline_totale_secondi=3.5)
        )
        assert politica_configurata.deadline_totale_secondi == 3.5

    def test_le_credenziali_nell_url_non_finiscono_nei_log(
        self,
        db_session: Session,
        contesto: Contesto,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        feed = collega(
            db_session,
            contesto,
            "https://utente:segretissima@feed.example.com/calendario.ics",
        )
        trasporto = ClientFeedHttp(
            politica(reti_consentite=()), risolutore=lambda host: ["10.1.2.3"]
        )

        with caplog.at_level("DEBUG"):
            sincronizza(db_session, feed, trasporto)

        # `caplog.text` è reso con DEFAULT_LOG_FORMAT e gli attributi passati
        # via `extra=` NON vi finiscono mai: asserire su di esso sarebbe
        # tautologico — passerebbe anche loggando l'URL in chiaro, e anche
        # cancellando del tutto le chiamate a `logger`. Si asserisce sui
        # RECORD, e in positivo sulla forma redatta.
        con_url = [record for record in caplog.records if hasattr(record, "url")]
        assert con_url, "nessun log ha registrato l'URL: il presidio non è esercitato"
        for record in con_url:
            assert "segretissima" not in record.url
            assert record.url == "https://***@feed.example.com/calendario.ics"
        # Le sedi sono DUE (trasporto e service): pretenderle entrambe, o
        # cancellarne una lascerebbe il test verde con metà presidio.
        moduli = {record.name for record in con_url}
        assert any("trasporto" in nome for nome in moduli), moduli
        assert any("service" in nome for nome in moduli), moduli


class TestJobDurevole:
    """AC 1 e AD-10: il percorso completo, dal job al worker."""

    def test_il_worker_esegue_il_sync_accodato_dal_collegamento(
        self,
        db_session: Session,
        contesto: Contesto,
        server_feed: ServerFeed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core.config import get_settings
        from app.core.jobs import run_due_jobs

        # Il client di produzione legge la politica dalla configurazione: la
        # si punta al loopback per esercitare DAVVERO `client_di_produzione`
        # invece di iniettare un client e non provare nulla su di esso.
        monkeypatch.setenv("HOSTPILOT_FEED_RETI_CONSENTITE", "127.0.0.0/8")
        get_settings.cache_clear()
        try:
            url = server_feed.prepara(
                "/calendario.ics",
                RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
            )
            feed = collega(db_session, contesto, url)

            completati = run_due_jobs(db_session)
            db_session.commit()
        finally:
            get_settings.cache_clear()

        assert completati == 1
        assert len(prenotazioni(db_session, feed)) == 2
        assert (
            service.ultimo_run(db_session, feed.host_id, feed.id).esito
            is EsitoSyncRun.RIUSCITO
        )

    def test_il_tipo_di_job_e_a_catalogo(self) -> None:
        from app.calendario.jobs import TIPO_JOB_SYNC_FEED
        from app.core.events import catalog

        assert TIPO_JOB_SYNC_FEED in catalog.job_names()

    def test_il_payload_del_job_porta_solo_identificatori(self) -> None:
        from app.calendario.jobs import TIPO_JOB_SYNC_FEED
        from app.core.events import catalog

        assert catalog.job(TIPO_JOB_SYNC_FEED).payload_keys == frozenset(
            {"feed_id", "host_id"}
        )


class TestTenancy:
    """AC 8: nessuna lettura cross-tenant."""

    def test_un_host_non_vede_i_feed_di_un_altro(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        altro = crea_host(db_session, "altro.host@example.com")
        sua_struttura = crea_struttura(db_session, altro.id, "Altra")
        db_session.commit()

        assert service.lista_feed(db_session, altro.id, sua_struttura.id) == []
        assert service.prenotazioni_del_feed(db_session, altro.id, feed.id) == []
        assert service.ultimo_run(db_session, altro.id, feed.id) is None
        with pytest.raises(service.FeedNonTrovatoError):
            service.esegui_sync(db_session, altro.id, feed.id, client=client())


class TestSemantica:
    """La finestra temporale resta quella di AD-3, anche dopo il round-trip."""

    def test_il_soggiorno_riletto_dal_db_e_semiaperto(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260814")
                )
            ),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        riga = prenotazioni(db_session, feed)[0]
        assert riga.soggiorno.nights == 4
        assert riga.soggiorno.contains(riga.check_in)
        assert not riga.soggiorno.contains(riga.check_out)

    def test_un_run_di_un_feed_inesistente_solleva(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        with pytest.raises(service.FeedNonTrovatoError):
            service.esegui_sync(
                db_session, contesto.host_id, uuid.uuid4(), client=client()
            )

    def test_l_intervallo_fra_iniziato_e_concluso_e_coerente(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())

        assert run.concluso_il - run.iniziato_il < timedelta(seconds=30)
