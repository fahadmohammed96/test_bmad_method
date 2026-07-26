"""AC 4 e AC 5 della Story 2.2 — `ETag`/`If-Modified-Since` e il 304.

**Questo file esiste per un rischio preciso**, il peggiore dell'Epic 2
(R2-C): un `304` — o una risposta vuota, o troncata — letto come «gli eventi
sono spariti dal feed» marcherebbe `rimossa_dal_feed` l'intero calendario,
con esito RIUSCITO e quindi senza che nessuna superficie lo segnali. I
Conflitti aperti su quelle Prenotazioni `decadrebbero`, e una doppia
prenotazione smetterebbe di essere segnalata.

Il difetto vive nell'**interazione** fra i due AC — la richiesta condizionale
e l'import append-preserving — quindi nessun test del singolo AC lo vede.
Per questo qui il 304 non si prepara a mano: il server lo produce
CONFRONTANDO il validatore che il client gli ha mandato. Un 304 preparato a
tavolino proverebbe che il codice sa leggere un 304, non che sappia chiedere
in modo condizionale, e la differenza fra le due cose è l'AC 4 per intero.

Rete stub-ata al TRASPORTO (server HTTP su 127.0.0.1), mai mockando il client
dentro il service: con un mock `ETag`, 304 e intestazioni realmente inviate
sparirebbero dal mondo e il test misurerebbe il mock.

Nessun dato reale di Ospiti nei fixture (NFR-16).
"""

import pytest
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import (
    CategoriaErroreSync,
    EsitoSyncRun,
    FeedIcal,
    StatoPrenotazione,
)
from app.calendario.trasporto import Validatori
from tests.calendario import (
    Contesto,
    calendario,
    client,
    collega,
    prenotazioni,
    sincronizza,
    vevent,
)
from tests.server_feed import RispostaPreparata, ServerFeed

PERCORSO = "/calendario.ics"
ETAG = '"v1-del-portale"'
ETAG_NUOVO = '"v2-del-portale"'
DATA_HTTP = "Sat, 25 Jul 2026 08:00:00 GMT"

DUE_EVENTI = calendario(
    vevent("uid-1@example.com", dal="20260810", al="20260812"),
    vevent("uid-2@example.com", dal="20260901", al="20260903"),
)


def _corpo(**validatori: str) -> RispostaPreparata:
    return RispostaPreparata(corpo=DUE_EVENTI, **validatori)


@pytest.fixture
def feed_con_etag(
    db_session: Session, contesto: Contesto, server_feed: ServerFeed
) -> FeedIcal:
    """Feed già importato una volta da un portale che espone un `ETag`."""
    server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
    feed = collega(db_session, contesto, server_feed.url(PERCORSO))
    sincronizza(db_session, feed, client())
    server_feed.richieste.clear()
    return feed


def intestazioni(server: ServerFeed, indice: int = -1) -> dict[str, str]:
    """Le intestazioni REALMENTE arrivate al server, normalizzate."""
    assert server.richieste, "il client non ha fatto alcuna richiesta"
    _, _, testa = server.richieste[indice]
    return {chiave.lower(): valore for chiave, valore in testa.items()}


class TestValidatoriMemorizzati:
    """AC 4 — i validatori si conservano solo da un import davvero riuscito."""

    def test_un_import_riuscito_memorizza_etag_e_last_modified(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG, last_modified=DATA_HTTP))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        sincronizza(db_session, feed, client())

        db_session.refresh(feed)
        assert feed.etag == ETAG
        assert feed.last_modified == DATA_HTTP

    def test_un_run_fallito_non_memorizza_nulla(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il cuore della sicurezza del meccanismo. Un validatore scritto su un
        # corpo che NON è stato riconciliato farebbe rispondere 304 a un feed
        # che nel database non è mai arrivato: il Feed resterebbe vuoto
        # dichiarandosi aggiornato, per sempre e in silenzio.
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(corpo=b"<html>manutenzione</html>", etag=ETAG),
        )
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.FALLITO
        db_session.refresh(feed)
        assert feed.etag is None
        assert feed.last_modified is None

    def test_una_risposta_senza_validatori_azzera_quelli_vecchi(
        self, db_session: Session, server_feed: ServerFeed, feed_con_etag: FeedIcal
    ) -> None:
        # Fondere invece di sostituire lascerebbe in giro un `If-None-Match`
        # che il portale non ha più modo di soddisfare — e se per qualunque
        # ragione lo soddisfacesse, il Feed resterebbe fermo su un validatore
        # che non descrive più niente.
        server_feed.prepara(PERCORSO, _corpo())

        sincronizza(db_session, feed_con_etag, client())

        db_session.refresh(feed_con_etag)
        assert feed_con_etag.etag is None

    def test_il_validatore_aggiornato_sostituisce_il_precedente(
        self, db_session: Session, server_feed: ServerFeed, feed_con_etag: FeedIcal
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG_NUOVO))

        sincronizza(db_session, feed_con_etag, client())

        db_session.refresh(feed_con_etag)
        assert feed_con_etag.etag == ETAG_NUOVO


class TestRichiestaCondizionale:
    """AC 4 — la correttezza sta negli header REALMENTE inviati sul filo."""

    def test_il_secondo_giro_manda_if_none_match(
        self, db_session: Session, server_feed: ServerFeed, feed_con_etag: FeedIcal
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))

        sincronizza(db_session, feed_con_etag, client())

        assert intestazioni(server_feed).get("if-none-match") == ETAG

    def test_il_secondo_giro_manda_if_modified_since(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo(last_modified=DATA_HTTP))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        sincronizza(db_session, feed, client())
        server_feed.richieste.clear()

        sincronizza(db_session, feed, client())

        assert intestazioni(server_feed).get("if-modified-since") == DATA_HTTP

    def test_la_data_si_rimanda_VERBATIM(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Riformattarla la renderebbe diversa da quella che il portale ha
        # emesso: il confronto fallirebbe SEMPRE, il 304 non arriverebbe mai,
        # e il sintomo sarebbe l'assenza di un risparmio — cioè nessun
        # sintomo. Un difetto che si manifesta solo come «non succede la cosa
        # buona» non si scopre da solo.
        esotica = "Sat, 25 Jul 2026 08:00:00 GMT"
        server_feed.prepara(PERCORSO, _corpo(last_modified=esotica))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        sincronizza(db_session, feed, client())
        server_feed.richieste.clear()

        sincronizza(db_session, feed, client())

        assert intestazioni(server_feed)["if-modified-since"] == esotica

    def test_il_primo_giro_non_manda_alcun_condizionale(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        sincronizza(db_session, feed, client())

        testa = intestazioni(server_feed)
        assert "if-none-match" not in testa
        assert "if-modified-since" not in testa

    def test_i_condizionali_sopravvivono_a_un_redirect(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Il validatore serve sull'hop FINALE, che è quello che risponde. Se
        # si perdesse lungo la catena il risparmio sparirebbe in silenzio
        # esattamente sui Feed che passano da un redirect — cioè quelli di
        # più portali reali.
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
        server_feed.prepara(
            "/vai",
            RispostaPreparata(
                stato=302, intestazioni={"Location": server_feed.url(PERCORSO)}
            ),
        )
        feed = collega(db_session, contesto, server_feed.url("/vai"))
        sincronizza(db_session, feed, client())
        server_feed.richieste.clear()

        sincronizza(db_session, feed, client())

        percorsi = [percorso for _, percorso, _ in server_feed.richieste]
        assert percorsi == ["/vai", PERCORSO]
        assert intestazioni(server_feed, 0)["if-none-match"] == ETAG
        assert intestazioni(server_feed, 1)["if-none-match"] == ETAG


class TestTrecentoQuattro:
    """AC 5 (P0) — R2-C: un 304 non tocca NIENTE, e il run è riuscito."""

    @pytest.fixture
    def feed_popolato_con_etag(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> FeedIcal:
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        sincronizza(db_session, feed, client())
        assert len(prenotazioni(db_session, feed)) == 2
        return feed

    def test_un_304_lascia_le_prenotazioni_esattamente_come_stavano(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        prima = {
            riga.ical_uid: (riga.stato, riga.check_in, riga.check_out)
            for riga in prenotazioni(db_session, feed_popolato_con_etag)
        }

        run = sincronizza(db_session, feed_popolato_con_etag, client())

        # Prima l'invariante di DATO: se cade questo è una doppia
        # prenotazione ospitata, non un'etichetta sbagliata.
        assert run.prenotazioni_rimosse_dal_feed == 0
        dopo = {
            riga.ical_uid: (riga.stato, riga.check_in, riga.check_out)
            for riga in prenotazioni(db_session, feed_popolato_con_etag)
        }
        assert dopo == prima
        assert set(dopo) == {"uid-1@example.com", "uid-2@example.com"}
        assert {stato for stato, _, _ in dopo.values()} == {StatoPrenotazione.ATTIVA}

    def test_un_304_scrive_un_sync_run_RIUSCITO(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        run = sincronizza(db_session, feed_popolato_con_etag, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.categoria_errore is None
        assert run.non_modificato is True
        # Nessuna riconciliazione: tutti i contatori a zero, ed è la
        # differenza fra «non c'era nulla di nuovo» e «abbiamo riletto tutto».
        assert run.prenotazioni_importate == 0
        assert run.prenotazioni_aggiornate == 0
        assert run.prenotazioni_ricomparse == 0

    def test_un_304_FA_avanzare_dati_aggiornati_alle(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        # Scelta esplicita, ed è il verso giusto di NFR-2: con un 304 abbiamo
        # davvero verificato col portale che i dati che mostriamo sono
        # correnti. Non farlo avanzare farebbe invecchiare l'etichetta su un
        # Feed sano finché l'Host non conclude che è rotto.
        prima = service.ultimo_run_riuscito(
            db_session, feed_popolato_con_etag.host_id, feed_popolato_con_etag.id
        )
        assert prima is not None

        sincronizza(db_session, feed_popolato_con_etag, client())

        dopo = service.ultimo_run_riuscito(
            db_session, feed_popolato_con_etag.host_id, feed_popolato_con_etag.id
        )
        assert dopo is not None
        assert dopo.id != prima.id
        assert dopo.concluso_il >= prima.concluso_il
        assert dopo.non_modificato is True

    def test_un_304_azzera_i_fallimenti_consecutivi(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=503))
        sincronizza(db_session, feed_popolato_con_etag, client())
        stato = service.stato_del_feed(
            db_session, feed_popolato_con_etag.host_id, feed_popolato_con_etag
        )
        assert stato.fallimenti_consecutivi == 1

        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
        sincronizza(db_session, feed_popolato_con_etag, client())

        stato = service.stato_del_feed(
            db_session, feed_popolato_con_etag.host_id, feed_popolato_con_etag
        )
        assert stato.fallimenti_consecutivi == 0

    def test_molti_304_di_fila_non_erodono_nulla(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        # Il poller gira ogni quindici minuti: se il 304 erodesse anche solo
        # una Prenotazione per giro, il danno sarebbe totale entro un giorno.
        for _ in range(5):
            run = sincronizza(db_session, feed_popolato_con_etag, client())
            assert run.non_modificato is True

        righe = prenotazioni(db_session, feed_popolato_con_etag)
        assert len(righe) == 2
        assert {riga.stato for riga in righe} == {StatoPrenotazione.ATTIVA}

    def test_dopo_un_304_un_200_con_meno_eventi_riconcilia_di_nuovo(
        self,
        db_session: Session,
        server_feed: ServerFeed,
        feed_popolato_con_etag: FeedIcal,
    ) -> None:
        # L'altra metà: la guardia non deve diventare un'inibizione generale.
        # Quando il portale RIMANDA il calendario, la transizione degli
        # scomparsi è di nuovo corretta e dovuta.
        sincronizza(db_session, feed_popolato_con_etag, client())
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812")
                ),
                etag=ETAG_NUOVO,
            ),
        )

        run = sincronizza(db_session, feed_popolato_con_etag, client())

        assert run.esito is EsitoSyncRun.RIUSCITO
        assert run.non_modificato is False
        assert run.prenotazioni_rimosse_dal_feed == 1


class TestContatoriDiagnosticiAttraversoUn304:
    """P1-6 — un 304 non deve azzerare ciò che la superficie mostra all'Host.

    `eventi_malformati` e `eventi_ricorrenti_non_espansi` sono avvisi: dicono
    all'Host che alcune righe del suo calendario non sono state importate. Se
    li si deriva dall'ultimo run RIUSCITO, un 304 — che è riuscito e ha tutti
    i contatori a zero — li spegne. Il portale non ha cambiato niente,
    **quindi gli eventi illeggibili ci sono ancora**: l'avviso sparirebbe
    esattamente perché il problema è rimasto identico.

    La verità temporale continua a venire dall'ultimo run riuscito (un 304 è
    una verifica riuscita); i CONTEGGI vengono dall'ultimo run che ha
    davvero riconciliato.
    """

    UID_ROTTO = (
        "BEGIN:VEVENT\r\nUID:rotto@example.com\r\n"
        "DTSTART;VALUE=DATE:20260812\r\nDTEND;VALUE=DATE:20260810\r\n"
        "SUMMARY:date invertite\r\nEND:VEVENT\r\n"
    )

    @pytest.fixture
    def feed_con_avvisi(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> FeedIcal:
        server_feed.prepara(
            PERCORSO,
            RispostaPreparata(
                corpo=calendario(
                    vevent("uid-1@example.com", dal="20260810", al="20260812"),
                    self.UID_ROTTO,
                ),
                etag=ETAG,
            ),
        )
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        run = sincronizza(db_session, feed, client())
        assert run.eventi_malformati == 1, "il fixture non produce l'avviso atteso"
        return feed

    def _stato(self, db: Session, feed: FeedIcal):
        return service.stato_del_feed(db, feed.host_id, feed)

    def test_un_304_non_spegne_l_avviso_sugli_eventi_malformati(
        self, db_session: Session, server_feed: ServerFeed, feed_con_avvisi: FeedIcal
    ) -> None:
        assert self._stato(db_session, feed_con_avvisi).eventi_malformati == 1

        run = sincronizza(db_session, feed_con_avvisi, client())

        assert run.non_modificato is True
        assert self._stato(db_session, feed_con_avvisi).eventi_malformati == 1

    def test_molti_304_di_fila_non_erodono_l_avviso(
        self, db_session: Session, server_feed: ServerFeed, feed_con_avvisi: FeedIcal
    ) -> None:
        for _ in range(4):
            sincronizza(db_session, feed_con_avvisi, client())

        assert self._stato(db_session, feed_con_avvisi).eventi_malformati == 1

    def test_il_timestamp_invece_AVANZA_col_304(
        self, db_session: Session, server_feed: ServerFeed, feed_con_avvisi: FeedIcal
    ) -> None:
        # Le due letture divergono di proposito, e vanno pinnate insieme:
        # il 304 è una verifica riuscita (quindi l'orario avanza) ma non è una
        # riconciliazione (quindi i conteggi restano quelli dell'ultima).
        prima = self._stato(db_session, feed_con_avvisi).ultimo_sync_riuscito_il
        assert prima is not None

        sincronizza(db_session, feed_con_avvisi, client())

        dopo = self._stato(db_session, feed_con_avvisi)
        assert dopo.ultimo_sync_riuscito_il is not None
        assert dopo.ultimo_sync_riuscito_il >= prima
        assert dopo.eventi_malformati == 1

    def test_un_200_che_risolve_il_problema_spegne_l_avviso(
        self, db_session: Session, server_feed: ServerFeed, feed_con_avvisi: FeedIcal
    ) -> None:
        # L'altra metà: l'avviso non deve diventare permanente. Quando il
        # portale manda davvero un calendario pulito, il conteggio torna a zero.
        sincronizza(db_session, feed_con_avvisi, client())
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG_NUOVO))

        sincronizza(db_session, feed_con_avvisi, client())

        assert self._stato(db_session, feed_con_avvisi).eventi_malformati == 0

    def test_un_feed_che_ha_SOLO_run_da_304_non_inventa_conteggi(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Confine: se non c'è mai stata una riconciliazione, i conteggi sono
        # zero perché non si sa, non perché sono stati misurati.
        server_feed.prepara(PERCORSO, _corpo(etag=ETAG))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        stato = service.stato_del_feed(db_session, feed.host_id, feed)

        assert stato.eventi_malformati == 0
        assert stato.eventi_ricorrenti_non_espansi == 0


class TestUn304NonSollecitato:
    """Un 304 vale solo come risposta a una domanda che abbiamo fatto."""

    def test_senza_validatori_memorizzati_un_304_e_un_esito_inatteso(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        # Se non abbiamo mandato validatori non c'è nulla che il portale possa
        # aver confrontato: quel 304 non afferma «è tutto uguale». Accettarlo
        # come run riuscito congelerebbe il Feed per sempre — l'import non
        # ripartirebbe mai, e ogni superficie continuerebbe a dichiararlo
        # aggiornato.
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=304))
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))

        run = sincronizza(db_session, feed, client())

        assert run.esito is EsitoSyncRun.FALLITO
        assert run.categoria_errore is CategoriaErroreSync.ESITO_HTTP_INATTESO
        assert run.non_modificato is False

    def test_un_304_non_sollecitato_non_tocca_le_prenotazioni(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        server_feed.prepara(PERCORSO, _corpo())
        feed = collega(db_session, contesto, server_feed.url(PERCORSO))
        sincronizza(db_session, feed, client())
        server_feed.prepara(PERCORSO, RispostaPreparata(stato=304))

        run = sincronizza(db_session, feed, client())

        assert run.prenotazioni_rimosse_dal_feed == 0
        righe = prenotazioni(db_session, feed)
        assert len(righe) == 2
        assert {riga.stato for riga in righe} == {StatoPrenotazione.ATTIVA}


class TestValidatoriUnita:
    """Il tipo che decide COSA si manda: confini, senza rete."""

    def test_senza_nulla_non_produce_intestazioni(self) -> None:
        assert Validatori().intestazioni() == {}
        assert not Validatori()

    def test_stringhe_vuote_non_sono_validatori(self) -> None:
        # Una colonna che torna `""` invece di `NULL` produrrebbe un
        # `If-None-Match: ` vuoto: sintatticamente una richiesta
        # condizionale, semanticamente niente. È il modo in cui un dato
        # degenere diventa un comportamento.
        assert Validatori(etag="", last_modified="").intestazioni() == {}
        assert not Validatori(etag="")

    def test_manda_entrambi_quando_ci_sono_entrambi(self) -> None:
        assert Validatori(etag=ETAG, last_modified=DATA_HTTP).intestazioni() == {
            "If-None-Match": ETAG,
            "If-Modified-Since": DATA_HTTP,
        }
