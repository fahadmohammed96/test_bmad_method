"""API di `calendario` (AC 1, 5, 6): /api/v1/feed-ical.

Qui si verifica ciò che l'Host vede: l'errore inline immediato, il progresso
dell'import, e che le credenziali eventualmente incollate nell'URL non tornino
mai indietro in una risposta (NFR-17).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.jobs import run_due_jobs
from tests.server_feed import RispostaPreparata, ServerFeed

PROBLEM = "application/problem+json"

DATI_STRUTTURA = {
    "nome": "Appartamento di prova",
    "comune": "Bologna",
    "regione": "Emilia-Romagna",
}

FEED_MINIMO = (
    b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
    b"UID:api-1@example.com\r\n"
    b"DTSTART;VALUE=DATE:20260810\r\nDTEND;VALUE=DATE:20260814\r\n"
    b"SUMMARY:Prenotazione inventata\r\n"
    b"END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def _accedi(client: TestClient, email: str = "host.di.prova@example.com") -> None:
    client.post(
        "/api/v1/auth/registrazione",
        json={"email": email, "password": "una-password-lunga"},
    )


def _struttura(client: TestClient, nome: str = DATI_STRUTTURA["nome"]) -> str:
    risposta = client.post("/api/v1/strutture", json={**DATI_STRUTTURA, "nome": nome})
    return risposta.json()["id"]


def _collega(client: TestClient, struttura_id: str, url: str, canale: str = "airbnb"):
    return client.post(
        "/api/v1/feed-ical",
        json={"struttura_id": struttura_id, "url": url, "canale": canale},
    )


class TestCollegamento:
    def test_collegare_un_feed_risponde_201_con_import_in_corso(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _collega(
            client, struttura_id, "https://feed.example.com/calendario.ics"
        )

        assert risposta.status_code == 201
        corpo = risposta.json()
        assert corpo["struttura_id"] == struttura_id
        assert corpo["canale"] == "airbnb"
        # Il job è accodato: l'Host deve poter mostrare «Importazione in
        # corso…» senza inventarsi lo stato lato client (AD-14).
        assert corpo["stato_sync"] == "in_corso"
        assert corpo["ultimo_sync_riuscito_il"] is None
        assert corpo["prenotazioni_attive"] == 0

    @pytest.mark.parametrize(
        "url", ["file:///etc/passwd", "webcal://feed.example.com/c.ics", "non-un-url"]
    )
    def test_un_url_non_valido_e_un_422_inline(
        self, client: TestClient, url: str
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _collega(client, struttura_id, url)

        assert risposta.status_code == 422
        assert risposta.headers["content-type"].startswith(PROBLEM)
        corpo = risposta.json()
        assert corpo["type"].endswith("url-feed-non-valido")
        assert "http" in (corpo.get("detail") or "")

    def test_le_credenziali_nell_url_non_tornano_al_client(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)

        risposta = _collega(
            client,
            struttura_id,
            "https://utente:segretissima@feed.example.com/calendario.ics",
        )

        assert risposta.status_code == 201
        assert "segretissima" not in risposta.text
        assert risposta.json()["url"] == "https://***@feed.example.com/calendario.ics"

    def test_la_struttura_di_un_altro_host_non_si_trova(
        self, client: TestClient
    ) -> None:
        _accedi(client, email="host.a@example.com")
        struttura_id = _struttura(client)
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")

        risposta = _collega(
            client, struttura_id, "https://feed.example.com/calendario.ics"
        )

        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("struttura-not-found")

    def test_senza_sessione_si_ottiene_401(self, client: TestClient) -> None:
        risposta = client.get(
            "/api/v1/feed-ical",
            params={"struttura_id": "00000000-0000-0000-0000-000000000000"},
        )
        assert risposta.status_code == 401


class TestLettura:
    def test_la_lista_e_scopata_per_struttura_e_per_host(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        prima = _struttura(client, "Prima")
        seconda = _struttura(client, "Seconda")
        _collega(client, prima, "https://feed.example.com/uno.ics")
        _collega(client, seconda, "https://feed.example.com/due.ics")

        della_prima = client.get(
            "/api/v1/feed-ical", params={"struttura_id": prima}
        ).json()
        assert [riga["url"] for riga in della_prima] == [
            "https://feed.example.com/uno.ics"
        ]

    def test_un_feed_inesistente_e_404(self, client: TestClient) -> None:
        _accedi(client)
        risposta = client.get("/api/v1/feed-ical/00000000-0000-0000-0000-000000000000")
        assert risposta.status_code == 404
        assert risposta.json()["type"].endswith("feed-ical-not-found")

    def test_dopo_l_import_l_api_mostra_progresso_e_prenotazioni(
        self,
        client: TestClient,
        pg_engine: Engine,
        server_feed: ServerFeed,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Il percorso completo: collegamento via API → job → import → lettura.
        monkeypatch.setenv("HOSTPILOT_FEED_RETI_CONSENTITE", "127.0.0.0/8")
        get_settings.cache_clear()
        try:
            _accedi(client)
            struttura_id = _struttura(client)
            url = server_feed.prepara(
                "/calendario.ics", RispostaPreparata(corpo=FEED_MINIMO)
            )
            feed_id = _collega(client, struttura_id, url).json()["id"]

            with Session(pg_engine) as db:
                assert run_due_jobs(db) == 1
                db.commit()
        finally:
            get_settings.cache_clear()

        corpo = client.get(f"/api/v1/feed-ical/{feed_id}").json()
        assert corpo["stato_sync"] == "riuscito"
        assert corpo["prenotazioni_attive"] == 1
        assert corpo["ultimo_sync_riuscito_il"] is not None

        prenotazioni = client.get(f"/api/v1/feed-ical/{feed_id}/prenotazioni").json()
        assert len(prenotazioni) == 1
        assert prenotazioni[0]["check_in"] == "2026-08-10"
        assert prenotazioni[0]["check_out"] == "2026-08-14"
        assert prenotazioni[0]["notti"] == 4
        assert prenotazioni[0]["stato"] == "attiva"

    def test_un_url_verso_la_rete_interna_fallisce_come_irraggiungibile(
        self, client: TestClient, pg_engine: Engine
    ) -> None:
        # L'URL passa la validazione SINCRONA di formato (è http, ha un host):
        # è la politica di uscita di rete a fermarlo nel job, e l'Host vede lo
        # stato d'errore sulla Struttura entro il primo run (§4.2-1).
        # Nessun DNS: l'indirizzo è letterale, quindi il rifiuto non tocca la
        # rete nemmeno per risolvere.
        _accedi(client)
        struttura_id = _struttura(client)
        collegato = _collega(client, struttura_id, "http://10.1.2.3/calendario.ics")
        assert collegato.status_code == 201
        feed_id = collegato.json()["id"]

        with Session(pg_engine) as db:
            run_due_jobs(db)
            db.commit()

        dettaglio = client.get(f"/api/v1/feed-ical/{feed_id}")
        corpo = dettaglio.json()
        assert corpo["stato_sync"] == "fallito"
        # Stessa categoria di una connessione fallita: la risposta non dice
        # che l'indirizzo era privato (NFR-17).
        assert corpo["categoria_errore"] == "url_non_raggiungibile"
        assert corpo["ultimo_sync_riuscito_il"] is None
        assert "privat" not in dettaglio.text.lower()


class TestContrattoDeiCanali:
    def test_i_canali_ammessi_sono_quelli_del_glossario(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura_id = _struttura(client)
        for canale in ("airbnb", "booking", "altro"):
            assert (
                _collega(
                    client,
                    struttura_id,
                    f"https://feed.example.com/{canale}.ics",
                    canale,
                ).status_code
                == 201
            )
        assert (
            _collega(
                client, struttura_id, "https://feed.example.com/x.ics", "vrbo"
            ).status_code
            == 422
        )

    def test_la_politica_di_default_non_ammette_reti_locali(self) -> None:
        # Difesa in profondità: anche se un ambiente puntasse il feed al
        # loopback, il default della configurazione non lo permette.
        from app.calendario.uscita_rete import (
            DestinazioneNonAmmessaError,
            PoliticaUscitaRete,
            valida_destinazione,
            valida_formato,
        )

        politica = PoliticaUscitaRete.da_configurazione(get_settings())
        assert politica.reti_consentite == ()
        # E la conseguenza che conta: con quella politica il loopback e' un
        # indirizzo VIETATO. Asserirlo sull'esito, non sulla tupla vuota —
        # `any()` su una tupla appena dichiarata vuota non puo' fallire.
        with pytest.raises(DestinazioneNonAmmessaError):
            valida_destinazione(
                valida_formato("http://127.0.0.1/calendario.ics"),
                politica,
                lambda host: [],
            )
