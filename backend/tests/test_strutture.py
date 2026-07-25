"""Test del modulo `strutture` (Story 1.4, FR-1): registrazione con cap di
3 unità attive, CIN opzionale non bloccante, archiviazione mai distruzione
(AD-20), tenancy (AD-2), eventi outbox nella stessa transazione (AD-1).

Nessun dato reale nei fixture (NFR-16).
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.outbox import OutboxEvent

PROBLEM = "application/problem+json"

DATI = {"nome": "Bologna Centro", "comune": "Bologna", "regione": "Emilia-Romagna"}


def _accedi(client: TestClient, email: str = "host.di.prova@example.com") -> None:
    client.post(
        "/api/v1/auth/registrazione",
        json={"email": email, "password": "una-password-lunga"},
    )


def _crea(client: TestClient, **extra):
    return client.post("/api/v1/strutture", json={**DATI, **extra})


class TestCreazione:
    def test_crea_struttura_con_campi_minimi(self, client: TestClient) -> None:
        _accedi(client)
        response = _crea(client)
        assert response.status_code == 201
        body = response.json()
        assert body["nome"] == DATI["nome"]
        assert body["comune"] == "Bologna"
        assert body["regione"] == "Emilia-Romagna"
        assert body["stato"] == "attiva"

    def test_nome_comune_regione_obbligatori(self, client: TestClient) -> None:
        _accedi(client)
        response = client.post("/api/v1/strutture", json={"nome": "Solo nome"})
        assert response.status_code == 422

    def test_cin_opzionale_con_indicatore_non_bloccante(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        senza_cin = _crea(client).json()
        assert senza_cin["cin"] is None
        assert senza_cin["cin_mancante"] is True  # indicatore, mai un blocco

        con_cin = _crea(client, nome="Con CIN", cin="IT01234567890AB").json()
        assert con_cin["cin_mancante"] is False

    def test_creazione_emette_evento_outbox_nella_stessa_transazione(
        self, client: TestClient, db_session: Session
    ) -> None:
        _accedi(client)
        struttura = _crea(client).json()
        evento = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_name == "struttura.creata")
        ).one()
        assert evento.payload["struttura_id"] == struttura["id"]


class TestCapTreAttive:
    def test_la_quarta_attiva_e_rifiutata_con_messaggio_pilota(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        for n in range(3):
            assert _crea(client, nome=f"Struttura {n + 1}").status_code == 201

        risposta = _crea(client, nome="Struttura 4")
        assert risposta.status_code == 409
        assert risposta.headers["content-type"].startswith(PROBLEM)
        corpo = risposta.json()
        assert "1-3" in (corpo.get("detail") or "") + corpo["title"]

    def test_archiviare_libera_un_posto(self, client: TestClient) -> None:
        _accedi(client)
        ids = [_crea(client, nome=f"S{n}").json()["id"] for n in range(3)]
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")
        assert _crea(client, nome="Nuova dopo archivio").status_code == 201

    def test_il_cap_e_per_host_non_globale(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        for n in range(3):
            _crea(client, nome=f"A{n}")
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")
        assert _crea(client, nome="B1").status_code == 201


class TestArchiviazione:
    def test_archivia_mai_distrugge(
        self, client: TestClient, db_session: Session
    ) -> None:
        _accedi(client)
        struttura_id = _crea(client).json()["id"]
        risposta = client.post(f"/api/v1/strutture/{struttura_id}/archivia")
        assert risposta.status_code == 200
        assert risposta.json()["stato"] == "archiviata"

        # La Struttura resta in lista (storico), con stato archiviata.
        lista = client.get("/api/v1/strutture").json()
        assert [s["stato"] for s in lista] == ["archiviata"]

        evento = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_name == "struttura.archiviata")
        ).one()
        assert evento.payload["struttura_id"] == struttura_id

    def test_archiviare_due_volte_e_idempotente(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _crea(client).json()["id"]
        client.post(f"/api/v1/strutture/{struttura_id}/archivia")
        seconda = client.post(f"/api/v1/strutture/{struttura_id}/archivia")
        assert seconda.status_code == 200
        assert seconda.json()["stato"] == "archiviata"


class TestModifica:
    def test_modifica_campi(self, client: TestClient) -> None:
        _accedi(client)
        struttura_id = _crea(client).json()["id"]
        risposta = client.patch(
            f"/api/v1/strutture/{struttura_id}",
            json={"nome": "Rinominata", "cin": "IT99999999999ZZ"},
        )
        assert risposta.status_code == 200
        assert risposta.json()["nome"] == "Rinominata"
        assert risposta.json()["cin_mancante"] is False


class TestTenancy:
    def test_ogni_host_vede_solo_le_sue_strutture(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        _crea(client, nome="Di A")
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")
        assert client.get("/api/v1/strutture").json() == []

    def test_agire_su_strutture_altrui_e_un_404(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        struttura_id = _crea(client).json()["id"]
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")

        assert (
            client.patch(
                f"/api/v1/strutture/{struttura_id}", json={"nome": "Rubata"}
            ).status_code
            == 404
        )
        assert (
            client.post(f"/api/v1/strutture/{struttura_id}/archivia").status_code == 404
        )
