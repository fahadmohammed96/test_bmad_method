"""Rilevazione dei Conflitti: lo STATO persistito (Story 2.5, AD-5, FR-5).

La regola è pura e sta in `test_conflitti_rilevazione.py`. Qui si verifica
ciò che quella regola non può dire da sola: che il chiamante le passi davvero
il solo insieme `attiva` di UNA Struttura, che rieseguire la rilevazione non
apra un secondo Conflitto per la stessa coppia, che l'identità sia
canonicalizzata **nel database**, e che la fonte mostrata all'Host sia quella
vera di ciascun lato — sono difetti diversi da quello del criterio, e nessuno
di essi è osservabile senza stato.
"""

import uuid
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendario import service
from app.calendario.models import CanaleFeed, Conflitto, StatoConflitto
from app.calendario.repository import ConflittoRepository, PrenotazioneRepository
from app.core.date_range import utcnow
from tests.calendario import (
    Contesto,
    client,
    collega,
    conflitti,
    crea_manuale,
    crea_prenotazione,
    crea_struttura,
    prenotazioni,
    sincronizza,
    vevent,
)
from tests.calendario import calendario as corpo_ical
from tests.server_feed import RispostaPreparata, ServerFeed

# Un soggiorno e un secondo che ne occupa l'ultima notte: la sovrapposizione
# minima, cioè quella che un confine sbagliato di un giorno perde.
PRIMO_ARRIVO = date(2026, 10, 1)
PRIMA_PARTENZA = date(2026, 10, 5)
SECONDO_ARRIVO = date(2026, 10, 4)
SECONDA_PARTENZA = date(2026, 10, 8)


def _rilevati(db: Session, contesto: Contesto) -> list[Conflitto]:
    return [
        riga
        for riga in conflitti(db, contesto)
        if riga.stato is StatoConflitto.RILEVATO
    ]


class TestAperturaDelConflitto:
    """AC 1, 2: due Prenotazioni sovrapposte, ESATTAMENTE un Conflitto."""

    def test_due_manuali_sovrapposte_aprono_un_conflitto(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prima = crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        seconda = crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        aperti = _rilevati(db_session, contesto)

        assert len(aperti) == 1
        coppia = {aperti[0].prenotazione_min_id, aperti[0].prenotazione_max_id}
        assert coppia == {prima.id, seconda.id}
        assert aperti[0].struttura_id == contesto.struttura_id
        assert aperti[0].decaduto_il is None

    def test_il_turnover_dello_stesso_giorno_non_apre_niente(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-3 al confine, sul percorso reale: chi parte il 5 e chi arriva il
        # 5 non si incontrano, ed è il caso NORMALE di un affitto breve. Un
        # `>=` al posto di un `>` aprirebbe un Conflitto a ogni cambio ospite.
        crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        crea_manuale(
            db_session,
            contesto,
            check_in=PRIMA_PARTENZA,
            check_out=PRIMA_PARTENZA + timedelta(days=3),
        )

        assert conflitti(db_session, contesto) == []

    def test_rieseguire_la_rilevazione_non_apre_un_secondo_conflitto(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # È la proprietà che il vincolo persistito difende, ed è diversa da
        # quella del criterio: la regola pura dà sempre la stessa coppia, ma
        # chi la scrive potrebbe inserirla ogni volta.
        crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        for _ in range(5):
            assert (
                service.rivaluta_conflitti(
                    db_session, contesto.host_id, contesto.struttura_id
                )
                == 0
            )
            db_session.commit()

        assert len(_rilevati(db_session, contesto)) == 1

    def test_e_l_IMPORT_a_rilevare_quando_arriva_la_seconda(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        """AC 1, metà «quando termina un import» (F2).

        L'ordine è il test. Ogni altro caso di questa suite crea la manuale
        **dopo** il sync, quindi al termine dell'import la sovrapposizione non
        esiste ancora e il Conflitto lo apre sempre il percorso manuale: la
        rilevazione dentro `esegui_sync` si poteva togliere e 142 test
        restavano verdi. Qui la manuale c'è già e la seconda Prenotazione
        arriva dal portale — che è il trigger più frequente nella vita reale,
        perché le prenotazioni arrivano dai portali.
        """
        manuale = crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        assert conflitti(db_session, contesto) == []

        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent("in-arrivo@example.com", dal="20261004", al="20261008")
                )
            ),
        )
        feed = collega(db_session, contesto, url)
        sincronizza(db_session, feed, client())

        aperti = _rilevati(db_session, contesto)
        assert len(aperti) == 1, (
            "l'import è terminato con una sovrapposizione e non ha rilevato "
            "niente: è il trigger dell'AC 1 che nessun altro test esercita"
        )
        da_feed = next(
            riga
            for riga in prenotazioni(db_session, feed)
            if riga.ical_uid == "in-arrivo@example.com"
        )
        assert {aperti[0].prenotazione_min_id, aperti[0].prenotazione_max_id} == {
            manuale.id,
            da_feed.id,
        }

    def test_tre_sovrapposte_a_due_a_due_aprono_tre_conflitti(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # §4.2-5 ratificato: l'unità è la coppia, non il gruppo. Cambia il
        # conteggio del badge (2.8) e la misura di SM-1.
        for arrivo in (1, 2, 3):
            crea_manuale(
                db_session,
                contesto,
                check_in=date(2026, 10, arrivo),
                check_out=date(2026, 10, 10),
            )

        assert len(_rilevati(db_session, contesto)) == 3

    def test_prenotazioni_di_strutture_diverse_non_si_incontrano_mai(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AC 10 al livello dello STATO: che il criterio sia scopato lo dice
        # l'unit test, che il chiamante gli passi il solo insieme della
        # Struttura lo dice solo questo.
        altra = crea_struttura(db_session, contesto.host_id, "Seconda Struttura")
        db_session.commit()
        crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        crea_manuale(
            db_session,
            contesto,
            struttura_id=altra.id,
            check_in=PRIMO_ARRIVO,
            check_out=PRIMA_PARTENZA,
        )

        assert conflitti(db_session, contesto) == []

    def test_una_prenotazione_non_attiva_non_partecipa(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # AD-19: solo `attiva` concorre. Una Prenotazione cancellata resta in
        # griglia con la sua etichetta, ma non è più un impegno.
        cancellata = crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        service.cancella_prenotazione(db_session, contesto.host_id, cancellata.id)
        crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        assert conflitti(db_session, contesto) == []


class TestIdentitaImpostaDalDatabase:
    """AC 3 (§4.2-4): la coppia non è ordinata, e a imporlo è lo schema."""

    def test_la_stessa_coppia_non_si_apre_due_volte(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prima = crea_prenotazione(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        seconda = crea_prenotazione(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )
        db_session.commit()
        conflitti_repo = ConflittoRepository(db_session)
        minore, maggiore = sorted((prima.id, seconda.id))

        primo = conflitti_repo.apri(
            contesto.host_id,
            struttura_id=contesto.struttura_id,
            prenotazione_min_id=minore,
            prenotazione_max_id=maggiore,
            adesso=utcnow(),
        )
        secondo = conflitti_repo.apri(
            contesto.host_id,
            struttura_id=contesto.struttura_id,
            prenotazione_min_id=minore,
            prenotazione_max_id=maggiore,
            adesso=utcnow(),
        )
        db_session.commit()

        assert primo is not None
        assert secondo is None, (
            "il secondo tentativo ha aperto un Conflitto: l'indice UNIQUE "
            "parziale non sta mordendo"
        )
        assert len(_rilevati(db_session, contesto)) == 1

    def test_la_coppia_scambiata_non_e_rappresentabile(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # L'altra metà, e senza di essa il vincolo sopra sarebbe aggirabile:
        # `(B,A)` è una riga diversa per l'indice, quindi la canonicalizzazione
        # deve essere impossibile da violare, non solo rispettata dal codice
        # che oggi scrive.
        prima = crea_prenotazione(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        seconda = crea_prenotazione(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )
        db_session.commit()
        minore, maggiore = sorted((prima.id, seconda.id))

        with pytest.raises(IntegrityError):
            ConflittoRepository(db_session).apri(
                contesto.host_id,
                struttura_id=contesto.struttura_id,
                prenotazione_min_id=maggiore,
                prenotazione_max_id=minore,
                adesso=utcnow(),
            )
            db_session.flush()
        db_session.rollback()

    def test_un_conflitto_decaduto_non_impedisce_di_riaprirne_uno(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # L'indice è PARZIALE apposta: se coprisse ogni stato, una coppia che
        # torna a sovrapporsi resterebbe senza segnalazione per sempre — cioè
        # il vincolo diventerebbe una perdita di Conflitti.
        prima = crea_prenotazione(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        seconda = crea_prenotazione(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )
        db_session.commit()
        conflitti_repo = ConflittoRepository(db_session)
        minore, maggiore = sorted((prima.id, seconda.id))
        conflitti_repo.apri(
            contesto.host_id,
            struttura_id=contesto.struttura_id,
            prenotazione_min_id=minore,
            prenotazione_max_id=maggiore,
            adesso=utcnow(),
        )
        # La transizione PRIMA del decadimento, e non è cerimonia: dal fix di
        # F1 un Conflitto decade solo se la Prenotazione è davvero fuori da
        # `attiva` adesso. L'allestimento precedente decadeva un Conflitto fra
        # due Prenotazioni vive — cioè costruiva uno stato che il prodotto non
        # produce, ed è esattamente il difetto che F1 ha chiuso.
        PrenotazioneRepository(db_session).marca_cancellata(
            contesto.host_id, prenotazione_id=prima.id, adesso=utcnow()
        )
        conflitti_repo.decadi_per_prenotazione(
            contesto.host_id, prenotazione_id=prima.id, adesso=utcnow()
        )
        db_session.commit()

        riaperto = conflitti_repo.apri(
            contesto.host_id,
            struttura_id=contesto.struttura_id,
            prenotazione_min_id=minore,
            prenotazione_max_id=maggiore,
            adesso=utcnow(),
        )
        db_session.commit()

        assert riaperto is not None
        assert len(conflitti(db_session, contesto)) == 2


class TestFonteEtimestamp:
    """AC 5 (§4.2-6): fonte e timestamp di CIASCUN lato, senza falsa simmetria."""

    def test_una_manuale_dichiara_di_non_essere_sincronizzata(
        self, db_session: Session, contesto: Contesto, server_feed: ServerFeed
    ) -> None:
        url = server_feed.prepara(
            "/calendario.ics",
            RispostaPreparata(
                corpo=corpo_ical(
                    vevent("conflitto-1@example.com", dal="20261001", al="20261005")
                )
            ),
        )
        feed = collega(db_session, contesto, url)
        run = sincronizza(db_session, feed, client())
        # AC 2 della Story 2.4: la manuale che si sovrappone a una da Feed è
        # il ponte fra le due sorgenti, e nessuno dei due percorsi presi da
        # solo lo attraversa.
        crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        vista = service.conflitti_rilevati(db_session, contesto.host_id)

        assert len(vista.conflitti) == 1
        lati = {
            lato.prenotazione.canale: lato for lato in vista.conflitti[0].prenotazioni
        }
        da_feed = lati[CanaleFeed.AIRBNB]
        assert da_feed.sincronizzata is True
        assert da_feed.aggiornata_il == run.concluso_il
        manuale = lati[CanaleFeed.MANUALE]
        assert manuale.sincronizzata is False, (
            "una Prenotazione manuale un sync non ce l'ha: dichiararla "
            "sincronizzata è la falsa simmetria che §4.2-6 vieta"
        )
        assert manuale.aggiornata_il == manuale.prenotazione.creata_il

    def test_i_due_lati_arrivano_in_ordine_cronologico(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        prima = crea_manuale(
            db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA
        )
        seconda = crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        vista = service.conflitti_rilevati(db_session, contesto.host_id)

        assert [lato.prenotazione.id for lato in vista.conflitti[0].prenotazioni] == [
            prima.id,
            seconda.id,
        ]

    def test_un_feed_mai_sincronizzato_dice_che_non_lo_sa(
        self, db_session: Session, contesto: Contesto
    ) -> None:
        # Il caso in cui la falsa sincronia farebbe il danno massimo: l'Host
        # sta scegliendo quale prenotazione tenere. Inventare un orario qui
        # sarebbe peggio di non averne uno.
        feed = collega(db_session, contesto, "https://feed.example.com/mai.ics")
        crea_prenotazione(
            db_session,
            contesto,
            check_in=PRIMO_ARRIVO,
            check_out=PRIMA_PARTENZA,
            canale=CanaleFeed.AIRBNB,
            feed_id=feed.id,
            ical_uid="mai-sincronizzato@example.com",
        )
        db_session.commit()
        crea_manuale(
            db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
        )

        vista = service.conflitti_rilevati(db_session, contesto.host_id)

        da_feed = next(
            lato
            for lato in vista.conflitti[0].prenotazioni
            if lato.prenotazione.canale is CanaleFeed.AIRBNB
        )
        assert da_feed.sincronizzata is True
        assert da_feed.aggiornata_il is None


class TestApiDeiConflitti:
    """La superficie: perimetro, verità temporale, tenancy (AD-2, NFR-14)."""

    def _host(self, http: TestClient, email: str) -> str:
        http.post(
            "/api/v1/auth/registrazione",
            json={"email": email, "password": "una-password-lunga"},
        )
        risposta = http.post(
            "/api/v1/strutture",
            json={
                "nome": "Appartamento di prova",
                "comune": "Bologna",
                "regione": "Emilia-Romagna",
            },
        )
        return risposta.json()["id"]

    def _prenota(
        self, http: TestClient, struttura_id: str, check_in: str, check_out: str
    ) -> None:
        risposta = http.post(
            "/api/v1/calendario/prenotazioni",
            json={
                "struttura_id": struttura_id,
                "check_in": check_in,
                "check_out": check_out,
            },
        )
        assert risposta.status_code == 201, risposta.text

    def test_i_conflitti_dell_host_con_i_due_lati(self, client: TestClient) -> None:
        struttura_id = self._host(client, "host.conflitti@example.com")
        self._prenota(client, struttura_id, "2026-10-01", "2026-10-05")
        self._prenota(client, struttura_id, "2026-10-04", "2026-10-08")

        risposta = client.get("/api/v1/conflitti")

        assert risposta.status_code == 200
        corpo = risposta.json()
        assert len(corpo["conflitti"]) == 1
        conflitto = corpo["conflitti"][0]
        assert conflitto["stato"] == "rilevato"
        assert conflitto["struttura_id"] == struttura_id
        assert [riga["check_in"] for riga in conflitto["prenotazioni"]] == [
            "2026-10-01",
            "2026-10-04",
        ]
        assert all(riga["sincronizzata"] is False for riga in conflitto["prenotazioni"])
        # La verità temporale del perimetro viaggia con la risposta (GS-7):
        # nessun Feed collegato è un'affermazione, non un silenzio.
        assert corpo["stato_sync"] == "mai_sincronizzato"
        assert corpo["ultimo_sync_riuscito_il"] is None

    def test_il_selettore_struttura_filtra_il_perimetro(
        self, client: TestClient
    ) -> None:
        struttura_id = self._host(client, "host.due.strutture@example.com")
        altra = client.post(
            "/api/v1/strutture",
            json={
                "nome": "Seconda Struttura",
                "comune": "Bologna",
                "regione": "Emilia-Romagna",
            },
        ).json()["id"]
        self._prenota(client, struttura_id, "2026-10-01", "2026-10-05")
        self._prenota(client, struttura_id, "2026-10-04", "2026-10-08")

        assert len(client.get("/api/v1/conflitti").json()["conflitti"]) == 1
        filtrati = client.get(f"/api/v1/conflitti?struttura_id={altra}").json()
        assert filtrati["conflitti"] == []

    def test_la_struttura_di_un_altro_host_e_un_404(self, client: TestClient) -> None:
        struttura_id = self._host(client, "host.primo@example.com")
        client.post("/api/v1/auth/logout")
        self._host(client, "host.secondo@example.com")

        risposta = client.get(f"/api/v1/conflitti?struttura_id={struttura_id}")

        assert risposta.status_code == 404
        assert risposta.headers["content-type"].startswith("application/problem+json")

    def test_i_conflitti_di_un_altro_host_non_si_vedono(
        self, client: TestClient
    ) -> None:
        struttura_id = self._host(client, "host.con.conflitto@example.com")
        self._prenota(client, struttura_id, "2026-10-01", "2026-10-05")
        self._prenota(client, struttura_id, "2026-10-04", "2026-10-08")
        client.post("/api/v1/auth/logout")
        self._host(client, "host.senza.conflitti@example.com")

        assert client.get("/api/v1/conflitti").json()["conflitti"] == []

    def test_senza_sessione_non_si_leggono_conflitti(self, client: TestClient) -> None:
        assert client.get("/api/v1/conflitti").status_code == 401


def test_la_rilevazione_ignora_una_struttura_di_un_altro_host(
    db_session: Session, contesto: Contesto
) -> None:
    # Un `host_id` che non possiede la Struttura non deve «vedere zero
    # Prenotazioni e aprire zero Conflitti» per caso: deve essere il filtro a
    # dirlo, e il filtro è in ogni metodo del repository (G-3, AD-2).
    crea_manuale(db_session, contesto, check_in=PRIMO_ARRIVO, check_out=PRIMA_PARTENZA)
    crea_manuale(
        db_session, contesto, check_in=SECONDO_ARRIVO, check_out=SECONDA_PARTENZA
    )
    estraneo = uuid.uuid4()

    assert service.rivaluta_conflitti(db_session, estraneo, contesto.struttura_id) == 0
