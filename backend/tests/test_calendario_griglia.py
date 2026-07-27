"""Calendario unificato (Story 2.3, FR-4) — il confine API e il suo perimetro.

Livello I del test design: qui vivono gli AC che parlano di **dati nella
risposta** e di **confine**, non di pixel. In particolare l'AC 7 (tenancy) sta
qui e non nella UI: la fuga di dati è un fatto della query, e si esercita dove
la query vive.

La griglia non compare in questo file. La mappatura intervallo → celle è una
funzione pura del frontend (AC 11) e si prova là, dove costa millisecondi.

Nessun dato reale di Ospiti (NFR-16).
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.calendario import service
from app.calendario.models import (
    CanaleFeed,
    EsitoSyncRun,
    Prenotazione,
    StatoPrenotazione,
)
from app.calendario.schemas import StatoSincronizzazione
from app.identity.models import Host
from app.strutture.service import StrutturaNonTrovataError
from tests.calendario import (
    Contesto,
    collega,
    crea_contesto,
    crea_prenotazione,
    crea_struttura,
    crea_sync_run,
    registra_ospite,
)

PROBLEM = "application/problem+json"
AGOSTO = (date(2026, 8, 1), date(2026, 8, 31))


def _griglia(db: Session, contesto: Contesto, **kwargs) -> service.Calendario:
    da, a = kwargs.pop("periodo", AGOSTO)
    return service.calendario(db, contesto.host_id, da=da, a=a, **kwargs)


class TestCosaMostraOgniPrenotazione:
    """AC 2: Canale d'origine, Struttura, date e Ospite."""

    def test_la_voce_porta_canale_struttura_date_e_notti(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
            canale=CanaleFeed.BOOKING,
        )
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.prenotazione.canale is CanaleFeed.BOOKING
        assert voce.prenotazione.struttura_id == contesto.struttura_id
        assert voce.prenotazione.check_in == date(2026, 8, 10)
        assert voce.prenotazione.check_out == date(2026, 8, 14)
        # `notti` è derivato dal server (AD-14): quattro notti, non cinque
        # giorni — l'intervallo è semiaperto (AD-3).
        assert voce.prenotazione.soggiorno.nights == 4

    def test_mostra_l_ospite_principale_e_conta_gli_altri(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
        )
        registra_ospite(
            db_session, contesto, prenotazione, nome="Intestatario", principale=True
        )
        db_session.flush()
        registra_ospite(db_session, contesto, prenotazione, nome="Accompagnatore")
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.ospite_principale == "Intestatario"
        assert voce.altri_ospiti == 1

    def test_un_solo_ospite_registrato_e_il_principale_anche_senza_flag(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # «L'unico noto, o quello indicato dall'Host»: con uno solo non c'è
        # niente da indicare.
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
        )
        registra_ospite(db_session, contesto, prenotazione, nome="Unico Noto")
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.ospite_principale == "Unico Noto"
        assert voce.altri_ospiti == 0

    def test_con_piu_ospiti_e_nessuno_indicato_non_se_ne_elegge_uno_d_ufficio(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Il primo inserito non è «il principale»: è il primo. Presentarlo
        # come tale sarebbe un'identità dedotta, cioè la stessa cosa che
        # l'invariante vieta di fare col `sommario`.
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
        )
        registra_ospite(db_session, contesto, prenotazione, nome="Primo")
        db_session.flush()
        registra_ospite(db_session, contesto, prenotazione, nome="Secondo")
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.ospite_principale is None
        assert voce.altri_ospiti == 2

    def test_una_prenotazione_SENZA_ospite_resta_valida(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Non è un errore e non è un caso degradato: è il caso normale di una
        # Prenotazione importata da un Feed, che un'identità Ospite non la
        # porta. La superficie scriverà «Ospite non indicato».
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
            sommario="Testo opaco del portale",
        )
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.ospite_principale is None
        assert voce.altri_ospiti == 0
        # E il `sommario` NON diventa il nome passando dall'API.
        assert voce.prenotazione.sommario == "Testo opaco del portale"

    def test_l_anagrafica_azzerata_non_resuscita_il_nome(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Dopo la retention la Prenotazione resta e l'Ospite pure, senza
        # nome: la griglia torna a dire «non indicato», non un vuoto ambiguo
        # e non il `sommario` al suo posto.
        prenotazione = crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
            sommario="Testo opaco del portale",
        )
        ospite = registra_ospite(
            db_session, contesto, prenotazione, nome="Da Azzerare", principale=True
        )
        db_session.flush()
        ospite.nome = None
        ospite.anonimizzato_il = datetime.now(UTC)
        db_session.commit()

        voce = _griglia(db_session, contesto).voci[0]

        assert voce.ospite_principale is None
        assert voce.altri_ospiti == 0


class TestPerimetroDelPeriodo:
    """Quali Prenotazioni entrano nella finestra richiesta (AD-3)."""

    def test_una_prenotazione_che_finisce_il_primo_giorno_visibile_e_fuori(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # `check_out` == `da`: l'ultima notte è il 31 luglio, e in agosto non
        # c'è nessun suo pernottamento. Con un confronto `>=` comparirebbe
        # in due mesi di fila, e l'Host la conterebbe due volte.
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 7, 28),
            check_out=date(2026, 8, 1),
        )
        db_session.commit()

        assert _griglia(db_session, contesto).voci == []

    def test_una_prenotazione_che_comincia_l_ultimo_giorno_visibile_e_dentro(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 31),
            check_out=date(2026, 9, 3),
        )
        db_session.commit()

        assert len(_griglia(db_session, contesto).voci) == 1

    def test_una_prenotazione_a_cavallo_del_mese_compare_in_entrambi(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 7, 30),
            check_out=date(2026, 8, 3),
        )
        db_session.commit()

        luglio = _griglia(
            db_session, contesto, periodo=(date(2026, 7, 1), date(2026, 7, 31))
        )
        assert len(luglio.voci) == 1
        assert len(_griglia(db_session, contesto).voci) == 1


class TestPrenotazioniNonAttive:
    """§4.2-12: AD-19 dice che non fanno Conflitti, non che spariscono."""

    @pytest.mark.parametrize(
        "stato",
        [StatoPrenotazione.CANCELLATA, StatoPrenotazione.RIMOSSA_DAL_FEED],
    )
    def test_restano_visibili_con_il_loro_stato(
        self, db_session: Session, contesto: Contesto, stato: StatoPrenotazione
    ) -> None:
        # Farle sparire senza traccia contraddirebbe «archiviare, mai
        # distruggere» agli occhi dell'Host, che quella prenotazione l'ha
        # vista ieri. Lo STATO viaggia con la voce: è il frontend a
        # presentarlo diversamente, non il server a nasconderla.
        crea_prenotazione(
            db_session,
            contesto,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
            stato=stato,
            cessata_il=datetime.now(UTC),
        )
        db_session.commit()

        voci = _griglia(db_session, contesto).voci

        assert [voce.prenotazione.stato for voce in voci] == [stato]


class TestSelettoreStruttura:
    """UX-DR1: aggregata e singola sono la stessa lettura con un filtro."""

    def test_senza_filtro_aggrega_tutte_le_strutture(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        seconda = crea_struttura(db_session, contesto.host_id, "Seconda Struttura")
        crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 3)
        )
        crea_prenotazione(
            db_session,
            contesto,
            struttura_id=seconda.id,
            check_in=date(2026, 8, 5),
            check_out=date(2026, 8, 7),
        )
        db_session.commit()

        vista = _griglia(db_session, contesto)

        assert len(vista.voci) == 2
        assert {riga.nome for riga in vista.strutture} == {
            "Appartamento di prova",
            "Seconda Struttura",
        }

    def test_con_il_filtro_resta_una_sola_struttura(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        seconda = crea_struttura(db_session, contesto.host_id, "Seconda Struttura")
        crea_prenotazione(
            db_session, contesto, check_in=date(2026, 8, 1), check_out=date(2026, 8, 3)
        )
        crea_prenotazione(
            db_session,
            contesto,
            struttura_id=seconda.id,
            check_in=date(2026, 8, 5),
            check_out=date(2026, 8, 7),
        )
        db_session.commit()

        vista = _griglia(db_session, contesto, struttura_id=seconda.id)

        assert [voce.prenotazione.struttura_id for voce in vista.voci] == [seconda.id]
        assert [riga.nome for riga in vista.strutture] == ["Seconda Struttura"]


class TestVeritaTemporaleAggregata:
    """AC 4 / NFR-2 / UX-DR6 su una vista che aggrega più Feed."""

    def test_senza_feed_collegati_non_si_promette_nessun_orario(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        vista = _griglia(db_session, contesto)

        assert vista.feed_collegati == 0
        assert vista.ultimo_sync_riuscito_il is None

    def test_l_orario_mostrato_e_quello_del_feed_PIU_VECCHIO(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        """Il minimo, non il massimo.

        Con due portali, uno sincronizzato due minuti fa e uno fermo da tre
        giorni, il massimo direbbe all'Host che il calendario è aggiornato a
        due minuti fa. È aritmeticamente vero e falso come affermazione sui
        dati che sta guardando: metà di quelli mostrati hanno tre giorni.
        """
        vecchio = collega(db_session, contesto, "https://uno.example.com/c.ics")
        recente = collega(
            db_session, contesto, "https://due.example.com/c.ics", CanaleFeed.BOOKING
        )
        adesso = datetime.now(UTC)
        crea_sync_run(db_session, vecchio, concluso_il=adesso - timedelta(days=3))
        crea_sync_run(db_session, recente, concluso_il=adesso - timedelta(minutes=2))
        db_session.commit()

        vista = _griglia(db_session, contesto)

        assert vista.feed_collegati == 2
        assert vista.ultimo_sync_riuscito_il is not None
        assert (adesso - vista.ultimo_sync_riuscito_il) > timedelta(days=2)

    def test_un_feed_mai_sincronizzato_azzera_la_promessa_di_freschezza(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Un orario che descrive solo metà dei Feed non descrive la vista.
        # Il sistema dice «non lo so», e dice anche quanti Feed sono muti.
        sincronizzato = collega(db_session, contesto, "https://uno.example.com/c.ics")
        collega(
            db_session, contesto, "https://due.example.com/c.ics", CanaleFeed.BOOKING
        )
        crea_sync_run(db_session, sincronizzato, concluso_il=datetime.now(UTC))
        db_session.commit()

        vista = _griglia(db_session, contesto)

        assert vista.ultimo_sync_riuscito_il is None
        assert vista.feed_mai_sincronizzati == 1

    def test_lo_stato_aggregato_prende_il_PEGGIORE(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        buono = collega(db_session, contesto, "https://uno.example.com/c.ics")
        rotto = collega(
            db_session, contesto, "https://due.example.com/c.ics", CanaleFeed.BOOKING
        )
        adesso = datetime.now(UTC)
        crea_sync_run(db_session, buono, concluso_il=adesso)
        crea_sync_run(db_session, rotto, concluso_il=adesso - timedelta(minutes=5))
        crea_sync_run(db_session, rotto, concluso_il=adesso, esito=EsitoSyncRun.FALLITO)
        db_session.commit()

        vista = _griglia(db_session, contesto)

        assert vista.stato is StatoSincronizzazione.FALLITO
        assert vista.feed_in_errore == 1

    def test_il_filtro_di_struttura_restringe_anche_i_feed(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Altrimenti la vista di una Struttura sana mostrerebbe l'errore del
        # Feed di un'altra, e viceversa una vista filtrata continuerebbe a
        # dirsi vecchia per colpa di un Feed che non sta guardando.
        seconda = crea_struttura(db_session, contesto.host_id, "Seconda Struttura")
        collega(db_session, contesto, "https://uno.example.com/c.ics")
        db_session.commit()

        vista = _griglia(db_session, contesto, struttura_id=seconda.id)

        assert vista.feed_collegati == 0


class TestTenancy:
    """AC 7 (P0): il calendario di un Host non mostra mai quello di un altro."""

    def test_le_prenotazioni_di_un_altro_host_non_entrano_mai(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        estraneo = crea_contesto(
            db_session, email="host.estraneo@example.com", nome="Altrove"
        )
        crea_prenotazione(
            db_session,
            estraneo,
            check_in=date(2026, 8, 10),
            check_out=date(2026, 8, 14),
        )
        db_session.commit()

        vista = _griglia(db_session, contesto)

        assert vista.voci == []
        assert vista.strutture == [
            service.StrutturaDelCalendario(
                id=contesto.struttura_id, nome="Appartamento di prova"
            )
        ]

    def test_filtrare_sulla_struttura_di_un_altro_host_non_la_trova(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # 404, non una vista vuota: una lista vuota direbbe «quella Struttura
        # esiste e non ha prenotazioni», che è già un'informazione di troppo.
        estraneo = crea_contesto(
            db_session, email="host.estraneo@example.com", nome="Altrove"
        )
        db_session.commit()

        with pytest.raises(StrutturaNonTrovataError):
            _griglia(db_session, contesto, struttura_id=estraneo.struttura_id)


class TestApi:
    """Il confine HTTP: sessione, formato, errori."""

    @staticmethod
    def _accedi(client: TestClient, email: str = "host.griglia@example.com") -> None:
        client.post(
            "/api/v1/auth/registrazione",
            json={"email": email, "password": "una-password-lunga"},
        )

    @staticmethod
    def _struttura(client: TestClient, nome: str = "Appartamento di prova") -> str:
        risposta = client.post(
            "/api/v1/strutture",
            json={"nome": nome, "comune": "Bologna", "regione": "Emilia-Romagna"},
        )
        return risposta.json()["id"]

    def test_senza_sessione_e_401(self, client: TestClient) -> None:
        risposta = client.get("/api/v1/calendario?da=2026-08-01&a=2026-08-31")

        assert risposta.status_code == 401

    def test_la_risposta_porta_la_verita_temporale_e_le_strutture(
        self, client: TestClient
    ) -> None:
        self._accedi(client)
        struttura_id = self._struttura(client)

        corpo = client.get("/api/v1/calendario?da=2026-08-01&a=2026-08-31").json()

        assert corpo["da"] == "2026-08-01"
        assert corpo["a"] == "2026-08-31"
        assert corpo["stato_sync"] == "mai_sincronizzato"
        assert corpo["ultimo_sync_riuscito_il"] is None
        assert corpo["feed_collegati"] == 0
        assert [riga["id"] for riga in corpo["strutture"]] == [struttura_id]
        assert corpo["voci"] == []

    def test_una_voce_porta_ospite_e_notti_gia_derivati(
        self, client: TestClient, pg_engine: Engine
    ) -> None:
        self._accedi(client)
        struttura_id = self._struttura(client)
        # L'anagrafica non ha ancora un percorso di scrittura via API: la
        # prima scrittura volontaria dell'Host è la Story 2.4. Qui si passa
        # comunque dal service, che è l'unico scrittore ammesso (AD-18).
        with sessionmaker(pg_engine)() as db:
            host_id = db.scalars(select(Host.id)).one()
            prenotazione = Prenotazione(
                host_id=host_id,
                struttura_id=uuid.UUID(struttura_id),
                canale=CanaleFeed.AIRBNB,
                check_in=date(2026, 8, 10),
                check_out=date(2026, 8, 14),
                sommario="Testo opaco del portale",
            )
            db.add(prenotazione)
            db.flush()
            service.registra_ospite(
                db,
                host_id,
                prenotazione.id,
                service.DatiOspite(nome="Ospite Inventato", principale=True),
            )
            db.commit()

        corpo = client.get("/api/v1/calendario?da=2026-08-01&a=2026-08-31").json()

        voce = corpo["voci"][0]
        assert voce["canale"] == "airbnb"
        assert voce["struttura_id"] == struttura_id
        assert voce["check_in"] == "2026-08-10"
        assert voce["check_out"] == "2026-08-14"
        assert voce["notti"] == 4
        assert voce["stato"] == "attiva"
        assert voce["ospite_principale"] == "Ospite Inventato"
        assert voce["altri_ospiti"] == 0
        assert voce["sommario"] == "Testo opaco del portale"

    def test_un_periodo_rovesciato_e_un_422_problem_json(
        self, client: TestClient
    ) -> None:
        self._accedi(client)

        risposta = client.get("/api/v1/calendario?da=2026-08-31&a=2026-08-01")

        assert risposta.status_code == 422
        assert risposta.headers["content-type"].startswith(PROBLEM)
        assert risposta.json()["type"].endswith("periodo-calendario-non-valido")

    def test_un_periodo_sconfinato_e_un_422_non_una_lettura_di_tutto(
        self, client: TestClient
    ) -> None:
        self._accedi(client)

        risposta = client.get("/api/v1/calendario?da=0001-01-01&a=9999-12-31")

        assert risposta.status_code == 422
        assert risposta.json()["type"].endswith("periodo-calendario-troppo-ampio")

    def test_la_struttura_di_un_altro_host_e_un_404(self, client: TestClient) -> None:
        self._accedi(client, email="host.a@example.com")
        struttura_id = self._struttura(client)
        client.cookies.clear()
        self._accedi(client, email="host.b@example.com")

        risposta = client.get(
            f"/api/v1/calendario?da=2026-08-01&a=2026-08-31&struttura_id={struttura_id}"
        )

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("struttura-not-found")
