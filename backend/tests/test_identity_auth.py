"""Test del modulo `identity` — registrazione e autenticazione Host (AD-15).

Password argon2id; sessione server-side con cookie HttpOnly Secure
SameSite=Lax; `host_id` risolto SOLO dalla sessione, mai da input client.
Nessun dato reale nei fixture (NFR-16): email di test su dominio example.
"""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.date_range import utcnow
from app.identity.models import Host, Sessione

EMAIL = "host.di.prova@example.com"
PASSWORD = "una-password-lunga"

PROBLEM = "application/problem+json"


def _registra(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/registrazione", json={"email": email, "password": password}
    )


class TestRegistrazione:
    def test_registrazione_crea_host_e_sessione(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = _registra(client)
        assert response.status_code == 201
        body = response.json()
        assert body["email"] == EMAIL
        assert "password" not in body and "password_hash" not in body

        host = db_session.scalars(select(Host)).one()
        assert host.email == EMAIL

    def test_password_salvata_con_argon2id(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        host = db_session.scalars(select(Host)).one()
        assert host.password_hash.startswith("$argon2id$")
        assert PASSWORD not in host.password_hash

    def test_cookie_di_sessione_httponly_secure_samesite_lax(
        self, client: TestClient
    ) -> None:
        response = _registra(client)
        set_cookie = response.headers["set-cookie"].lower()
        assert "httponly" in set_cookie
        assert "secure" in set_cookie
        assert "samesite=lax" in set_cookie

    def test_il_token_in_db_e_hashato_non_in_chiaro(
        self, client: TestClient, db_session: Session
    ) -> None:
        response = _registra(client)
        raw_token = response.cookies["hostpilot_session"]
        sessione = db_session.scalars(select(Sessione)).one()
        assert sessione.token_hash != raw_token
        assert raw_token not in sessione.token_hash

    def test_email_duplicata_rifiutata_case_insensitive(
        self, client: TestClient
    ) -> None:
        _registra(client)
        response = _registra(client, email=EMAIL.upper())
        assert response.status_code == 409
        assert response.headers["content-type"].startswith(PROBLEM)

    def test_email_non_valida_rifiutata(self, client: TestClient) -> None:
        response = _registra(client, email="non-una-email")
        assert response.status_code == 422

    def test_password_troppo_corta_rifiutata(self, client: TestClient) -> None:
        response = _registra(client, password="corta")
        assert response.status_code == 422


class TestLogin:
    def test_login_con_credenziali_valide(self, client: TestClient) -> None:
        _registra(client)
        client.cookies.clear()
        response = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert response.status_code == 200
        assert "hostpilot_session" in response.cookies

    def test_password_errata_401_problem_json(self, client: TestClient) -> None:
        _registra(client)
        client.cookies.clear()
        response = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "sbagliata!!"}
        )
        assert response.status_code == 401
        assert response.headers["content-type"].startswith(PROBLEM)

    def test_email_sconosciuta_stesso_errore_delle_credenziali_errate(
        self, client: TestClient
    ) -> None:
        # Nessuna enumerazione utenti: stessa risposta per email inesistente
        # e password errata.
        _registra(client)
        client.cookies.clear()
        r_password = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "sbagliata!!"}
        )
        r_email = client.post(
            "/api/v1/auth/login",
            json={"email": "ignoto@example.com", "password": PASSWORD},
        )
        assert r_email.status_code == r_password.status_code == 401
        assert r_email.json()["type"] == r_password.json()["type"]
        assert r_email.json()["title"] == r_password.json()["title"]


class TestSessione:
    def test_endpoint_protetto_senza_sessione_401(self, client: TestClient) -> None:
        response = client.get("/api/v1/hosts/me")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith(PROBLEM)

    def test_host_id_risolto_dalla_sessione_mai_da_input_client(
        self, client: TestClient
    ) -> None:
        _registra(client, email="host.a@example.com")
        host_a = client.get("/api/v1/hosts/me").json()

        client.cookies.clear()
        _registra(client, email="host.b@example.com")

        # Il client prova a impersonare l'Host A via query/header: ignorato,
        # vale solo la sessione.
        response = client.get(
            "/api/v1/hosts/me",
            params={"host_id": host_a["id"]},
            headers={"X-Host-Id": host_a["id"]},
        )
        assert response.status_code == 200
        assert response.json()["email"] == "host.b@example.com"
        assert response.json()["id"] != host_a["id"]

    def test_cookie_contraffatto_401(self, client: TestClient) -> None:
        client.cookies.set("hostpilot_session", "token-inventato")
        assert client.get("/api/v1/hosts/me").status_code == 401

    def test_sessione_scaduta_401(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        sessione = db_session.scalars(select(Sessione)).one()
        sessione.expires_at = utcnow() - timedelta(seconds=1)
        db_session.commit()
        assert client.get("/api/v1/hosts/me").status_code == 401

    def test_logout_invalida_la_sessione_server_side(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        raw_token = client.cookies["hostpilot_session"]
        response = client.post("/api/v1/auth/logout")
        assert response.status_code == 204
        assert db_session.scalars(select(Sessione)).all() == []

        # Anche ripresentando il vecchio token, la sessione non esiste più.
        client.cookies.set("hostpilot_session", raw_token)
        assert client.get("/api/v1/hosts/me").status_code == 401

    def test_me_restituisce_l_host_autenticato(self, client: TestClient) -> None:
        _registra(client)
        response = client.get("/api/v1/hosts/me")
        assert response.status_code == 200
        assert response.json()["email"] == EMAIL


@pytest.mark.usefixtures("client")
class TestMigrazioneIdentity:
    def test_host_e_sessione_esistono(self, db_session: Session) -> None:
        # La fixture di sessione applica `alembic upgrade head`: se le
        # tabelle mancano, i test sopra falliscono prima; qui verifichiamo
        # il vincolo NOT NULL di host_id sulla tabella di sessione (AD-2).
        from sqlalchemy import inspect

        colonne = {
            c["name"]: c for c in inspect(db_session.bind).get_columns("sessione")
        }
        assert colonne["host_id"]["nullable"] is False
