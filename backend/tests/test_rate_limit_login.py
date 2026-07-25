"""Test del freno ai tentativi di login ripetuti (G-5, AD-15).

Due limiti complementari, entrambi su FINESTRA temporale — mai un
lockout permanente: uno per account (protegge il singolo Host preso di
mira) e uno per origine (protegge dallo spraying su molti account).
Il freno non deve mai rivelare se un'email esiste.
"""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.date_range import utcnow
from app.identity.models import TentativoLogin

EMAIL = "host.di.prova@example.com"
PASSWORD = "una-password-lunga"

PROBLEM = "application/problem+json"


def _registra(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/registrazione", json={"email": EMAIL, "password": PASSWORD}
    )
    client.cookies.clear()


def _login(client: TestClient, *, email: str = EMAIL, password: str = "sbagliata!!"):
    return client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )


def _invecchia_i_tentativi(db: Session, minuti: int) -> None:
    """Sposta indietro nel tempo i tentativi registrati (finestra scaduta)."""
    db.execute(
        update(TentativoLogin).values(avvenuto_il=utcnow() - timedelta(minutes=minuti))
    )
    db.commit()


class TestLimitePerAccount:
    def test_oltre_la_soglia_il_login_e_429(self, client: TestClient) -> None:
        _registra(client)
        soglia = get_settings().login_max_tentativi_account

        for _ in range(soglia):
            assert _login(client).status_code == 401

        bloccato = _login(client)
        assert bloccato.status_code == 429
        assert bloccato.headers["content-type"].startswith(PROBLEM)

    def test_il_429_dice_quando_riprovare(self, client: TestClient) -> None:
        _registra(client)
        for _ in range(get_settings().login_max_tentativi_account):
            _login(client)

        bloccato = _login(client)
        assert int(bloccato.headers["retry-after"]) > 0

    def test_anche_la_password_giusta_e_frenata_finche_dura_la_finestra(
        self, client: TestClient
    ) -> None:
        _registra(client)
        for _ in range(get_settings().login_max_tentativi_account):
            _login(client)

        assert _login(client, password=PASSWORD).status_code == 429

    def test_dopo_la_finestra_il_login_legittimo_funziona(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Nessun lockout permanente: passata la finestra si riparte.
        _registra(client)
        for _ in range(get_settings().login_max_tentativi_account):
            _login(client)
        assert _login(client, password=PASSWORD).status_code == 429

        _invecchia_i_tentativi(db_session, get_settings().login_finestra_minuti + 1)

        risposta = _login(client, password=PASSWORD)
        assert risposta.status_code == 200
        assert "hostpilot_session" in risposta.cookies

    def test_il_login_riuscito_azzera_i_tentativi_dell_account(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        for _ in range(get_settings().login_max_tentativi_account - 1):
            _login(client)

        assert _login(client, password=PASSWORD).status_code == 200
        client.cookies.clear()

        rimasti = db_session.scalars(
            select(TentativoLogin).where(TentativoLogin.email == EMAIL)
        ).all()
        assert rimasti == []
        # E si può sbagliare di nuovo senza restare bloccati subito.
        assert _login(client).status_code == 401

    def test_il_freno_non_rivela_se_l_email_esiste(self, client: TestClient) -> None:
        # Stessa risposta per un account inesistente: nessuna enumerazione.
        soglia = get_settings().login_max_tentativi_account
        for _ in range(soglia):
            assert _login(client, email="ignoto@example.com").status_code == 401

        bloccato = _login(client, email="ignoto@example.com")
        assert bloccato.status_code == 429


class TestLimitePerOrigine:
    def test_lo_spraying_su_molti_account_viene_frenato(
        self, client: TestClient
    ) -> None:
        # Sotto la soglia per account, ma molti account dalla stessa
        # origine: è il caso che il solo limite per account non vede.
        settings = get_settings()
        assert (
            settings.login_max_tentativi_origine > settings.login_max_tentativi_account
        )

        for n in range(settings.login_max_tentativi_origine):
            assert _login(client, email=f"vittima{n}@example.com").status_code == 401

        bloccato = _login(client, email="ennesima@example.com")
        assert bloccato.status_code == 429

    def test_dopo_la_finestra_l_origine_torna_libera(
        self, client: TestClient, db_session: Session
    ) -> None:
        settings = get_settings()
        for n in range(settings.login_max_tentativi_origine):
            _login(client, email=f"vittima{n}@example.com")
        assert _login(client, email="ennesima@example.com").status_code == 429

        _invecchia_i_tentativi(db_session, settings.login_finestra_minuti + 1)
        assert _login(client, email="ennesima@example.com").status_code == 401


class TestTracce:
    def test_il_tentativo_non_registra_mai_la_password(
        self, client: TestClient, db_session: Session
    ) -> None:
        _registra(client)
        _login(client, password="segretissima-da-non-salvare")

        colonne = {c.name for c in TentativoLogin.__table__.columns}
        assert "password" not in colonne
        tentativo = db_session.scalars(select(TentativoLogin)).one()
        assert "segretissima" not in str(tentativo.__dict__)

    def test_il_purge_periodico_ripulisce_i_tentativi_vecchi(
        self, client: TestClient, db_session: Session
    ) -> None:
        # Le tracce del freno sono effimere: le pulisce lo stesso job
        # periodico delle sessioni, così la tabella resta limitata.
        from app.identity.jobs import purge_sessioni_scadute

        _registra(client)
        _login(client)
        _invecchia_i_tentativi(db_session, get_settings().login_finestra_minuti * 10)

        purge_sessioni_scadute(db_session, {})
        db_session.commit()

        assert db_session.scalars(select(TentativoLogin)).all() == []
