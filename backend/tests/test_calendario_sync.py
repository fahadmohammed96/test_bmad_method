"""Integration del sync dei Feed iCal (Story 2.1) su PostgreSQL reale.

La rete si stub-a **al trasporto**, con un server HTTP su 127.0.0.1
(`tests/server_feed.py`): redirect, `Content-Length`, chiusura anticipata,
timeout e cap di dimensione *sono* il comportamento sotto test, e un mock a
livello di service li cancellerebbe dal mondo — il test finirebbe per
misurare il mock (retrospettiva Epic 1 §3.3).

Nessun dato reale di Ospiti nei fixture (NFR-16).
"""

import ipaddress
import time
import uuid
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

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
from app.calendario.trasporto import ClientFeedHttp
from app.calendario.uscita_rete import PoliticaUscitaRete, UrlFeedNonValidoError
from app.core.date_range import utcnow
from app.core.jobs import Job, JobStatus
from app.identity.models import Host
from app.strutture.models import Struttura
from app.strutture.service import StrutturaNonTrovataError
from tests.server_feed import RispostaPreparata, ServerFeed

FIXTURES = Path(__file__).parent / "fixtures" / "ical"
LOOPBACK = (ipaddress.ip_network("127.0.0.0/8"),)


def fixture_ical(nome: str) -> bytes:
    return (FIXTURES / nome).read_bytes()


def calendario(*eventi: str) -> bytes:
    corpo = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n" + "".join(eventi) + "END:VCALENDAR\r\n"
    return corpo.encode("utf-8")


def vevent(uid: str, *, dal: str, al: str, extra: str = "") -> str:
    return (
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}\r\n"
        f"DTSTART;VALUE=DATE:{dal}\r\n"
        f"DTEND;VALUE=DATE:{al}\r\n"
        f"SUMMARY:Prenotazione inventata {uid}\r\n"
        f"{extra}"
        "END:VEVENT\r\n"
    )


def politica(
    *,
    cap: int = 1_000_000,
    lettura: float = 5.0,
    max_redirect: int = 3,
    deadline: float = 30.0,
    reti_consentite: tuple = LOOPBACK,
) -> PoliticaUscitaRete:
    return PoliticaUscitaRete(
        timeout_connessione_secondi=2.0,
        timeout_lettura_secondi=lettura,
        dimensione_massima_byte=cap,
        max_redirect=max_redirect,
        deadline_totale_secondi=deadline,
        reti_consentite=reti_consentite,
    )


def client(**kwargs) -> ClientFeedHttp:
    """Client REALE con la politica del test: il confine resta la socket."""
    return ClientFeedHttp(politica(**kwargs))


@dataclass(frozen=True, slots=True)
class Contesto:
    host_id: uuid.UUID
    struttura_id: uuid.UUID


def _host(db: Session, email: str) -> Host:
    host = Host(email=email, password_hash="$argon2id$finto")
    db.add(host)
    db.flush()
    return host


def _struttura(db: Session, host_id: uuid.UUID, nome: str) -> Struttura:
    struttura = Struttura(
        host_id=host_id, nome=nome, comune="Testopoli", regione="Emilia-Romagna"
    )
    db.add(struttura)
    db.flush()
    return struttura


@pytest.fixture
def contesto(db_session: Session) -> Contesto:
    host = _host(db_session, "host.di.prova@example.com")
    struttura = _struttura(db_session, host.id, "Appartamento di prova")
    db_session.commit()
    return Contesto(host_id=host.id, struttura_id=struttura.id)


def collega(
    db: Session, contesto: Contesto, url: str, canale: CanaleFeed = CanaleFeed.AIRBNB
) -> FeedIcal:
    return service.collega_feed(
        db,
        contesto.host_id,
        service.DatiFeed(struttura_id=contesto.struttura_id, url=url, canale=canale),
    )


def sincronizza(db: Session, feed: FeedIcal, trasporto: ClientFeedHttp):
    run = service.esegui_sync(db, feed.host_id, feed.id, client=trasporto)
    db.commit()
    return run


def prenotazioni(db: Session, feed: FeedIcal) -> list[Prenotazione]:
    return service.prenotazioni_del_feed(db, feed.host_id, feed.id)


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
        altro = _host(db_session, "altro.host@example.com")
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
                # timedelta esplode su una durata assurda: il regex accetta
                # cifre illimitate, `timedelta` no.
                "durata oltre i limiti di timedelta",
                calendario(
                    "BEGIN:VEVENT\r\nUID:ostile-durata@example.com\r\n"
                    "DTSTART;VALUE=DATE:20260810\r\nDURATION:P99999999D\r\n"
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
                "settimane oltre i limiti di timedelta",
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

    def test_un_redirect_da_https_a_http_e_rifiutato(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # L'URL del Feed porta il segreto in query: un declassamento lo
        # metterebbe in chiaro sul filo. `http` è ammesso in assoluto, ma non
        # DOPO `https`.
        from app.calendario.trasporto import UrlNonRaggiungibileError

        trasporto = ClientFeedHttp(politica())
        with pytest.raises(UrlNonRaggiungibileError):
            trasporto._vieta_declassamento(
                "https://feed.example.com/c.ics", "http://feed.example.com/c.ics"
            )
        # Il caso simmetrico è lecito: si può salire, non scendere.
        trasporto._vieta_declassamento(
            "http://feed.example.com/c.ics", "https://feed.example.com/c.ics"
        )

    def test_si_chiede_identity_e_non_si_ereditano_i_proxy_dall_ambiente(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # `Accept-Encoding: identity` toglie la decompressione illimitata di
        # `iter_bytes()`; `trust_env=False` impedisce che un HTTPS_PROXY
        # nell'ambiente del worker azzeri la denylist facendo risolvere il
        # nome al proxy.
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(corpo=fixture_ical("airbnb-date-only.ics")),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        _, _, intestazioni = server_feed.richieste[0]
        assert intestazioni["Accept-Encoding"] == "identity"

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
        run = sincronizza(db_session, feed, client(lettura=5.0, deadline=0.6))
        trascorso = time.monotonic() - inizio

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT
        # La deadline deve MORDERE, non essere una decorazione: senza di essa
        # il corpo (oltre 400 byte a 0.12s l'uno) impiegherebbe ~50 secondi.
        assert trascorso < 5.0

    def test_la_deadline_non_si_moltiplica_per_i_redirect(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il budget è dell'intero fetch: una catena di redirect lenti non deve
        # poter comprare tempo un hop alla volta.
        server_feed.prepara(
            "/uno.ics",
            RispostaPreparata(stato=302, intestazioni={"Location": "/due.ics"}),
        )
        server_feed.prepara(
            "/due.ics",
            RispostaPreparata(
                corpo=fixture_ical("airbnb-date-only.ics"), sgocciola_secondi=0.12
            ),
        )
        feed = collega(db_session, contesto, server_feed.url("/uno.ics"))

        inizio = time.monotonic()
        run = sincronizza(
            db_session, feed, client(lettura=5.0, deadline=0.6, max_redirect=3)
        )
        trascorso = time.monotonic() - inizio

        assert run.categoria_errore is CategoriaErroreSync.TIMEOUT
        assert trascorso < 5.0

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

        altro = _host(db_session, "altro.host@example.com")
        sua_struttura = _struttura(db_session, altro.id, "Altra")
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
