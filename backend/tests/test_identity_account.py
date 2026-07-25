"""Test del pannello Account (Story 1.3, UX-DR15): preferenze di notifica
e cambio password come infrastruttura di `identity` (AD-15, AD-18).
"""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import Sessione

EMAIL = "host.di.prova@example.com"
PASSWORD = "una-password-lunga"
NUOVA_PASSWORD = "una-password-nuova!"

PROBLEM = "application/problem+json"


def _registra(client: TestClient, email: str = EMAIL, password: str = PASSWORD):
    return client.post(
        "/api/v1/auth/registrazione", json={"email": email, "password": password}
    )


class TestPreferenzeNotifica:
    def test_default_canale_email(self, client: TestClient) -> None:
        _registra(client)
        me = client.get("/api/v1/hosts/me").json()
        assert me["canale_notifica_preferito"] == "email"

    def test_aggiorna_canale_preferito(self, client: TestClient) -> None:
        _registra(client)
        response = client.patch(
            "/api/v1/hosts/me/preferenze",
            json={"canale_notifica_preferito": "in_app"},
        )
        assert response.status_code == 200
        assert response.json()["canale_notifica_preferito"] == "in_app"
        # Persistito: una nuova lettura lo conferma.
        assert (
            client.get("/api/v1/hosts/me").json()["canale_notifica_preferito"]
            == "in_app"
        )

    def test_canale_non_valido_rifiutato(self, client: TestClient) -> None:
        _registra(client)
        response = client.patch(
            "/api/v1/hosts/me/preferenze",
            json={"canale_notifica_preferito": "piccione"},
        )
        assert response.status_code == 422


class TestCambioPassword:
    def test_password_attuale_errata_403(self, client: TestClient) -> None:
        _registra(client)
        response = client.post(
            "/api/v1/hosts/me/password",
            json={
                "password_attuale": "sbagliatissima",
                "password_nuova": NUOVA_PASSWORD,
            },
        )
        assert response.status_code == 403
        assert response.headers["content-type"].startswith(PROBLEM)

    def test_cambio_password_ruota_le_credenziali(self, client: TestClient) -> None:
        _registra(client)
        response = client.post(
            "/api/v1/hosts/me/password",
            json={"password_attuale": PASSWORD, "password_nuova": NUOVA_PASSWORD},
        )
        assert response.status_code == 204

        client.cookies.clear()
        vecchia = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}
        )
        assert vecchia.status_code == 401
        nuova = client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": NUOVA_PASSWORD}
        )
        assert nuova.status_code == 200

    def test_cambio_password_invalida_le_altre_sessioni(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        # Seconda sessione dello stesso Host (altro dispositivo).
        client.post("/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD})
        assert len(db_session.scalars(select(Sessione)).all()) == 2

        response = client.post(
            "/api/v1/hosts/me/password",
            json={"password_attuale": PASSWORD, "password_nuova": NUOVA_PASSWORD},
        )
        assert response.status_code == 204

        # Resta SOLO la sessione corrente, che continua a funzionare.
        db_session.expire_all()
        assert len(db_session.scalars(select(Sessione)).all()) == 1
        assert client.get("/api/v1/hosts/me").status_code == 200

    def test_password_nuova_troppo_corta_422(self, client: TestClient) -> None:
        _registra(client)
        response = client.post(
            "/api/v1/hosts/me/password",
            json={"password_attuale": PASSWORD, "password_nuova": "corta"},
        )
        assert response.status_code == 422


class TestCors:
    def test_preflight_dall_origin_del_frontend(self, client: TestClient) -> None:
        # L'app Next (localhost:3000) chiama l'API con credentials: il
        # backend deve rispondere al preflight con l'origin esplicita.
        response = client.options(
            "/api/v1/hosts/me",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "PATCH",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers["access-control-allow-origin"] == "http://localhost:3000"
        )
        assert response.headers["access-control-allow-credentials"] == "true"
