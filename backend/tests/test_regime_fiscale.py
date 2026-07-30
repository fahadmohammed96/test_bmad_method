"""Test del Regime fiscale derivato (Story 1.6, FR-17, AD-12).

Il Regime è SEMPRE derivato da `count(Strutture non archiviate)` alla
lettura, mai persistito. Soglia, aliquote citate e testo informativo sono
parametri in `config_normativa`, mai costanti nel codice. Il contenuto è
informativo con disclaimer: mai un calcolo d'imposta (Non-Goal PRD §8).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_normativa.models import ParametroFiscale
from app.core.outbox import OutboxEvent
from app.strutture.models import RegimeLettura
from app.strutture.repository import RegimeLetturaRepository

ADMIN_TOKEN = "token-di-test-per-endpoint-interni"


def _accedi(client: TestClient, email: str = "host.di.prova@example.com") -> None:
    client.post(
        "/api/v1/auth/registrazione",
        json={"email": email, "password": "una-password-lunga"},
    )


def _crea(client: TestClient, nome: str) -> dict:
    return client.post(
        "/api/v1/strutture",
        json={"nome": nome, "comune": "Testopoli", "regione": "Emilia-Romagna"},
    ).json()


def _regime(client: TestClient) -> dict:
    return client.get("/api/v1/regime-fiscale").json()


def _host_id(client: TestClient) -> uuid.UUID:
    return uuid.UUID(client.get("/api/v1/hosts/me").json()["id"])


def _letture(db: Session) -> list[RegimeLettura]:
    """Il registro delle conferme, in ordine di scrittura (PK UUIDv7)."""
    # `expire_all`: la sessione del test ha già letto queste righe prima che il
    # client le modificasse in una transazione propria, e senza scadenza
    # l'identity map le restituirebbe come stavano.
    db.expire_all()
    return list(db.scalars(select(RegimeLettura).order_by(RegimeLettura.id)))


@pytest.fixture
def parametri_fiscali(client: TestClient) -> None:
    """Soglia e testi vivono in configurazione, non nel codice (AD-12)."""
    risposta = client.put(
        "/api/v1/interno/parametri-fiscali",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "attore": "fahad@example.com",
            "soglia_strutture": 3,
            "regime_sotto_soglia": "cedolare_secca",
            "regime_da_soglia": "imprenditoriale",
            "testo_sotto_soglia": (
                "Con 1-2 Strutture rientri di norma nella cedolare secca."
            ),
            "testo_da_soglia": (
                "Con 3 Strutture cambia il tuo regime fiscale: scatta la "
                "presunzione di imprenditorialità e serve la Partita IVA."
            ),
            "aliquote_citate": "cedolare secca 21% / 26%",
            "valido_dal": "2026-01-01",
        },
    )
    assert risposta.status_code == 200


class TestDerivazione:
    def test_senza_strutture_nessuna_segnalazione(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client)
        regime = _regime(client)
        assert regime["strutture_non_archiviate"] == 0
        assert regime["oltre_soglia"] is False

    def test_una_o_due_strutture_indicano_la_cedolare(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client)
        _crea(client, "Prima")
        assert _regime(client)["regime"] == "cedolare_secca"
        _crea(client, "Seconda")
        regime = _regime(client)
        assert regime["regime"] == "cedolare_secca"
        assert regime["strutture_non_archiviate"] == 2
        assert regime["oltre_soglia"] is False

    def test_alla_terza_struttura_scatta_la_soglia(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client)
        for nome in ("Prima", "Seconda", "Terza"):
            _crea(client, nome)

        regime = _regime(client)
        assert regime["regime"] == "imprenditoriale"
        assert regime["oltre_soglia"] is True
        assert regime["soglia"] == 3
        assert "Partita IVA" in regime["testo"]
        assert regime["aliquote_citate"] == "cedolare secca 21% / 26%"

    def test_il_regime_non_e_mai_persistito(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        # AD-12: il Regime si deriva alla lettura. Nessuna colonna di
        # stato sulle entità: non può divergere dal conteggio.
        from app.identity.models import Host
        from app.strutture.models import Struttura

        for entita in (Struttura, Host):
            colonne = {c.name for c in entita.__table__.columns}
            assert not [c for c in colonne if "regime" in c or "fiscal" in c]

    def test_la_struttura_archiviata_esce_dal_conteggio(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client)
        ids = [_crea(client, f"S{n}")["id"] for n in range(3)]
        assert _regime(client)["oltre_soglia"] is True

        client.post(f"/api/v1/strutture/{ids[2]}/archivia")
        regime = _regime(client)
        assert regime["strutture_non_archiviate"] == 2
        assert regime["oltre_soglia"] is False
        assert regime["regime"] == "cedolare_secca"

    def test_il_conteggio_e_per_host(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client, email="host.a@example.com")
        for n in range(3):
            _crea(client, f"A{n}")
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")
        assert _regime(client)["oltre_soglia"] is False

    def test_richiede_una_sessione(self, client: TestClient) -> None:
        assert client.get("/api/v1/regime-fiscale").status_code == 401


class TestParametriInConfigurazione:
    def test_senza_parametri_configurati_degrada_in_sicurezza(
        self, client: TestClient
    ) -> None:
        # Nessun default inventato: senza configurazione non si segnala
        # un regime, si dichiara che non è disponibile (AD-9, AD-12).
        _accedi(client)
        _crea(client, "Prima")
        regime = _regime(client)
        assert regime["stato"] == "configurazione_non_disponibile"
        assert regime["regime"] is None
        assert regime["soglia"] is None

    def test_la_soglia_e_un_dato_non_una_costante(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        # NFR-4: se la legge cambiasse la soglia, basta un aggiornamento
        # dati — nessun rilascio di codice.
        _accedi(client)
        _crea(client, "Prima")
        _crea(client, "Seconda")
        assert _regime(client)["oltre_soglia"] is False

        client.put(
            "/api/v1/interno/parametri-fiscali",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={
                "attore": "fahad@example.com",
                "soglia_strutture": 2,
                "regime_sotto_soglia": "cedolare_secca",
                "regime_da_soglia": "imprenditoriale",
                "testo_sotto_soglia": "Sotto soglia.",
                "testo_da_soglia": "Da soglia: serve la Partita IVA.",
                "aliquote_citate": "aggiornate",
                "valido_dal": "2026-06-01",
            },
        )
        regime = _regime(client)
        assert regime["soglia"] == 2
        assert regime["oltre_soglia"] is True

    def test_la_soglia_fiscale_e_distinta_dal_cap_di_prodotto(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        # AD-12: il cap "max 3 attive" è un parametro di prodotto, la
        # soglia fiscale è normativa. Abbassare la soglia non tocca il cap.
        from app.core.config import get_settings

        client.put(
            "/api/v1/interno/parametri-fiscali",
            headers={"X-Admin-Token": ADMIN_TOKEN},
            json={
                "attore": "fahad@example.com",
                "soglia_strutture": 2,
                "regime_sotto_soglia": "cedolare_secca",
                "regime_da_soglia": "imprenditoriale",
                "testo_sotto_soglia": "Sotto soglia.",
                "testo_da_soglia": "Da soglia.",
                "aliquote_citate": "-",
                "valido_dal": "2026-01-01",
            },
        )
        _accedi(client)
        for n in range(3):
            assert _crea(client, f"S{n}").get("id") is not None
        assert get_settings().max_strutture_attive == 3

    def test_ogni_aggiornamento_dei_parametri_e_auditato(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        from app.config_normativa.models import ConfigAudit

        audit = db_session.scalars(
            select(ConfigAudit).where(ConfigAudit.entita == "parametro_fiscale")
        ).all()
        assert len(audit) == 1
        assert audit[0].attore == "fahad@example.com"
        assert audit[0].dati["soglia_strutture"] == 3

    def test_i_parametri_hanno_validita_temporale(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        parametri = db_session.scalars(select(ParametroFiscale)).all()
        assert len(parametri) == 1
        assert parametri[0].valido_al is None


class TestEventoDiTransizione:
    def test_superare_la_soglia_emette_un_evento(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        for nome in ("Prima", "Seconda", "Terza"):
            _crea(client, nome)

        eventi = db_session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.event_name == "regime_fiscale.soglia_superata"
            )
        ).all()
        assert len(eventi) == 1  # una sola volta, alla transizione

    def test_scendere_sotto_soglia_emette_il_rientro(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        ids = [_crea(client, f"S{n}")["id"] for n in range(3)]
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")

        eventi = db_session.scalars(
            select(OutboxEvent).where(
                OutboxEvent.event_name == "regime_fiscale.rientrato"
            )
        ).all()
        assert len(eventi) == 1

    def test_nessun_evento_finche_si_resta_sotto_soglia(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        _crea(client, "Prima")
        _crea(client, "Seconda")

        eventi = db_session.scalars(
            select(OutboxEvent).where(OutboxEvent.event_name.like("regime_fiscale.%"))
        ).all()
        assert eventi == []

    def test_il_pannello_va_mostrato_una_sola_volta_alla_transizione(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        # UX-DR14: pannello a schermo intero alla transizione, poi il
        # pannello persistente. Il flag è consumabile: niente notifiche
        # residue fuorvianti dopo la ridiscesa (UJ-4 edge).
        _accedi(client)
        ids = [_crea(client, f"S{n}")["id"] for n in range(3)]
        assert _regime(client)["mostra_pannello_transizione"] is True

        assert client.post("/api/v1/regime-fiscale/conferma-lettura").status_code == 204
        assert _regime(client)["mostra_pannello_transizione"] is False

        # Ridiscesa e nuova risalita: il pannello torna a essere dovuto.
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")
        assert _regime(client)["mostra_pannello_transizione"] is False
        _crea(client, "Nuova terza")
        assert _regime(client)["mostra_pannello_transizione"] is True


class TestRevocaTracciataDellaConferma:
    """Il rientro sotto soglia REVOCA la conferma, non la cancella (MYL-68).

    `conteggio_confermato` e `confermato_il` sono l'evidenza datata che l'Host è
    stato informato della soglia fiscale (UJ-4). Una `DELETE` perde la prova che
    lo sia mai stato — su una materia fiscale, dove la prova è il punto — e
    sarebbe una cancellazione distruttiva fuori dalla lista esaustiva di AD-20.
    Qui si pretende la forma di AD-19: transizione tracciata, riga che resta.
    """

    def _porta_a_tre_strutture(self, client: TestClient) -> list[str]:
        return [_crea(client, f"S{n}")["id"] for n in range(3)]

    def test_la_revoca_conserva_la_riga_e_la_sua_evidenza_datata(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        ids = self._porta_a_tre_strutture(client)
        client.post("/api/v1/regime-fiscale/conferma-lettura")

        client.post(f"/api/v1/strutture/{ids[0]}/archivia")

        letture = _letture(db_session)
        assert len(letture) == 1, "la revoca ha cancellato la riga"
        assert letture[0].conteggio_confermato == 3
        assert letture[0].confermato_il is not None
        assert letture[0].revocata_il is not None

    def test_dopo_la_revoca_la_conferma_non_vale_piu(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        # Il punto in cui questo cambiamento potrebbe rompere il comportamento
        # in silenzio: la riga resta, quindi «esiste una riga» non è più la
        # domanda giusta.
        _accedi(client)
        host_id = _host_id(client)
        ids = self._porta_a_tre_strutture(client)
        client.post("/api/v1/regime-fiscale/conferma-lettura")
        assert RegimeLetturaRepository(db_session).confermata(host_id) is True

        client.post(f"/api/v1/strutture/{ids[0]}/archivia")

        db_session.expire_all()
        assert RegimeLetturaRepository(db_session).confermata(host_id) is False

    def test_la_storia_dice_quando_e_stato_informato_e_quando_e_stata_revocata(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        # Requisito della decisione: chi guarda deve poter dire «informato il
        # giorno X, conferma revocata il giorno Y».
        _accedi(client)
        ids = self._porta_a_tre_strutture(client)
        client.post("/api/v1/regime-fiscale/conferma-lettura")
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")

        lettura = _letture(db_session)[0]
        assert lettura.revocata_il is not None
        assert lettura.revocata_il >= lettura.confermato_il

    def test_il_ciclo_conferma_revoca_riconferma_regge_due_giri(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        host_id = _host_id(client)
        repo = RegimeLetturaRepository(db_session)
        _crea(client, "Prima")
        _crea(client, "Seconda")

        for giro in range(2):
            terza = _crea(client, f"Terza del giro {giro}")["id"]
            assert _regime(client)["mostra_pannello_transizione"] is True

            client.post("/api/v1/regime-fiscale/conferma-lettura")
            db_session.expire_all()
            assert repo.confermata(host_id) is True
            assert _regime(client)["mostra_pannello_transizione"] is False

            client.post(f"/api/v1/strutture/{terza}/archivia")
            db_session.expire_all()
            assert repo.confermata(host_id) is False

        # Due conferme, due revoche: nessun giro ha sovrascritto il precedente.
        letture = _letture(db_session)
        assert len(letture) == 2
        assert [lettura.conteggio_confermato for lettura in letture] == [3, 3]
        assert all(lettura.revocata_il is not None for lettura in letture)

    def test_la_riconferma_apre_una_riga_nuova_e_lascia_intatta_la_revocata(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        _accedi(client)
        ids = self._porta_a_tre_strutture(client)
        client.post("/api/v1/regime-fiscale/conferma-lettura")
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")
        prima = _letture(db_session)[0]
        confermato_il, revocata_il = prima.confermato_il, prima.revocata_il

        _crea(client, "Nuova terza")
        client.post("/api/v1/regime-fiscale/conferma-lettura")

        letture = _letture(db_session)
        assert len(letture) == 2
        assert letture[0].confermato_il == confermato_il
        assert letture[0].revocata_il == revocata_il
        assert letture[1].revocata_il is None

    def test_una_conferma_ripetuta_non_moltiplica_le_righe(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        # Il registro cresce di un giro di soglia, non di un click: l'endpoint
        # è chiamabile a volontà e la conferma ATTIVA resta una.
        _accedi(client)
        self._porta_a_tre_strutture(client)

        for _ in range(3):
            client.post("/api/v1/regime-fiscale/conferma-lettura")

        assert len(_letture(db_session)) == 1

    def test_la_revoca_non_riscrive_la_data_di_una_conferma_gia_revocata(
        self, client: TestClient, parametri_fiscali: None, db_session: Session
    ) -> None:
        # Idempotenza sull'EVIDENZA, non solo sull'effetto: la data in cui la
        # conferma ha smesso di valere non si muove più.
        _accedi(client)
        host_id = _host_id(client)
        ids = self._porta_a_tre_strutture(client)
        client.post("/api/v1/regime-fiscale/conferma-lettura")
        client.post(f"/api/v1/strutture/{ids[0]}/archivia")
        revocata_il = _letture(db_session)[0].revocata_il

        RegimeLetturaRepository(db_session).revoca(host_id)
        db_session.flush()

        letture = _letture(db_session)
        assert len(letture) == 1
        assert letture[0].revocata_il == revocata_il


class TestContenutoInformativo:
    def test_il_disclaimer_e_sempre_presente(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        _accedi(client)
        _crea(client, "Prima")
        sotto_soglia = _regime(client)
        for nome in ("Seconda", "Terza"):
            _crea(client, nome)
        oltre_soglia = _regime(client)

        for regime in (sotto_soglia, oltre_soglia):
            assert regime["disclaimer"]
            assert "commercialista" in regime["disclaimer"].lower()

    def test_nessun_calcolo_di_imposta_nella_risposta(
        self, client: TestClient, parametri_fiscali: None
    ) -> None:
        # Non-Goal PRD §8: il prodotto informa, non calcola imposte.
        _accedi(client)
        for nome in ("Prima", "Seconda", "Terza"):
            _crea(client, nome)
        regime = _regime(client)

        vietati = {"imposta_cent", "imposta", "dovuto_cent", "totale_cent"}
        assert not vietati & set(regime)
