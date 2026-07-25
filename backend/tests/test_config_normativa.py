"""Test del modulo `config_normativa` (Story 1.5, FR-2, AD-9, NFR-4).

Anagrafica Comuni/Regioni da codici ISTAT, configurazione a validità
temporale, aggiornamenti solo via endpoint interni auditati, degrado
sicuro quando manca la configurazione — mai default inventati.

I codici ISTAT dei Comuni usati qui sono SINTETICI (anagrafica di test):
l'anagrafica reale si importa dal file ufficiale ISTAT.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config_normativa.models import Comune, ComuneConfig, ConfigAudit
from app.config_normativa.seed import REGIONI_ISTAT

PROBLEM = "application/problem+json"

ADMIN_TOKEN = "token-di-test-per-endpoint-interni"

# Anagrafica di test (codici sintetici, non ISTAT reali).
COMUNE_A = {"codice_istat": "T00001", "nome": "Testopoli", "provincia": "TS"}
COMUNE_B = {"codice_istat": "T00002", "nome": "Provaville", "provincia": "TS"}
REGIONE = "08"  # Emilia-Romagna


@pytest.fixture
def anagrafica(db_session: Session) -> None:
    for dati in (COMUNE_A, COMUNE_B):
        db_session.add(
            Comune(
                codice_istat=dati["codice_istat"],
                nome=dati["nome"],
                provincia=dati["provincia"],
                regione_codice_istat=REGIONE,
            )
        )
    db_session.commit()


def _accedi(client: TestClient, email: str = "host.di.prova@example.com") -> None:
    client.post(
        "/api/v1/auth/registrazione",
        json={"email": email, "password": "una-password-lunga"},
    )


def _crea_struttura(client: TestClient, **extra) -> dict:
    corpo = {
        "nome": "Casa di prova",
        "comune": COMUNE_A["nome"],
        "regione": "Emilia-Romagna",
        **extra,
    }
    return client.post("/api/v1/strutture", json=corpo).json()


def _stato(client: TestClient, struttura_id: str, **params) -> dict:
    return client.get(
        f"/api/v1/strutture/{struttura_id}/configurazione-normativa", params=params
    ).json()


def _configura_comune(
    client: TestClient,
    codice: str = COMUNE_A["codice_istat"],
    *,
    importo_cent: int = 200,
    valido_dal: str = "2026-01-01",
    valido_al: str | None = None,
    attore: str = "fahad@example.com",
):
    return client.put(
        f"/api/v1/interno/comuni/{codice}/configurazione",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "attore": attore,
            "tassa_importo_cent": importo_cent,
            "tassa_periodicita": "trimestrale",
            "esenzione_eta_max": 12,
            "esenzione_notti_oltre": 5,
            "valido_dal": valido_dal,
            "valido_al": valido_al,
        },
    )


def _configura_regione(client: TestClient, codice: str = REGIONE, **extra):
    return client.put(
        f"/api/v1/interno/regioni/{codice}/configurazione",
        headers={"X-Admin-Token": ADMIN_TOKEN},
        json={
            "attore": "fahad@example.com",
            "istat_tracciato": "ross1000-v2",
            "istat_periodicita": "mensile",
            "valido_dal": "2026-01-01",
            **extra,
        },
    )


class TestAnagrafica:
    def test_le_venti_regioni_sono_seedate_dai_codici_istat(
        self, client: TestClient
    ) -> None:
        regioni = client.get("/api/v1/regioni").json()
        assert len(regioni) == 20
        assert len(REGIONI_ISTAT) == 20
        emilia = next(r for r in regioni if r["codice_istat"] == "08")
        assert emilia["nome"] == "Emilia-Romagna"

    def test_ricerca_comuni_per_prefisso(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        risultati = client.get("/api/v1/comuni", params={"ricerca": "test"}).json()
        assert [c["nome"] for c in risultati] == ["Testopoli"]
        assert risultati[0]["codice_istat"] == COMUNE_A["codice_istat"]

    def test_ricerca_comuni_richiede_sessione(self, client: TestClient) -> None:
        risposta = client.get("/api/v1/comuni", params={"ricerca": "test"})
        assert risposta.status_code == 401


class TestTassaDiSoggiorno:
    def test_comune_non_riconosciuto_degrada_in_sicurezza(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(client, comune="Paese Inesistente")
        tassa = _stato(client, struttura["id"])["tassa_soggiorno"]

        assert tassa["stato"] == "configurazione_non_disponibile"
        assert tassa["motivo"] == "comune_non_riconosciuto"
        assert tassa["promemoria_manuale"] is True
        assert tassa["parametri"] is None  # mai un calcolo con default inventati

    def test_comune_riconosciuto_ma_non_configurato_degrada_in_sicurezza(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        tassa = _stato(client, struttura["id"])["tassa_soggiorno"]

        assert tassa["stato"] == "configurazione_non_disponibile"
        assert tassa["motivo"] == "comune_non_configurato"
        assert tassa["parametri"] is None

    def test_il_messaggio_ha_tono_informativo_non_di_colpa(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(client, comune="Paese Inesistente")
        messaggio = _stato(client, struttura["id"])["tassa_soggiorno"][
            "messaggio"
        ].lower()

        assert "ancora configurat" in messaggio  # "non è ancora configurata…"
        assert "a mano" in messaggio  # il promemoria manuale è dichiarato
        for parola_di_colpa in ("errore", "invalido", "non valido", "sbagliat"):
            assert parola_di_colpa not in messaggio

    def test_comune_configurato_espone_i_parametri(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        assert _configura_comune(client, importo_cent=250).status_code == 200

        tassa = _stato(client, struttura["id"])["tassa_soggiorno"]
        assert tassa["stato"] == "configurata"
        assert tassa["promemoria_manuale"] is False
        assert tassa["parametri"]["importo_cent"] == 250  # centesimi, mai float
        assert tassa["parametri"]["periodicita"] == "trimestrale"
        assert tassa["parametri"]["esenzione_eta_max"] == 12

    def test_configurazione_di_struttura_altrui_e_404(self, client: TestClient) -> None:
        _accedi(client, email="host.a@example.com")
        struttura = _crea_struttura(client)
        client.cookies.clear()
        _accedi(client, email="host.b@example.com")
        risposta = client.get(
            f"/api/v1/strutture/{struttura['id']}/configurazione-normativa"
        )
        assert risposta.status_code == 404


class TestIstat:
    def test_regione_configurata_espone_tracciato_e_periodicita(
        self, client: TestClient
    ) -> None:
        assert _configura_regione(client).status_code == 200
        _accedi(client)
        struttura = _crea_struttura(client)

        istat = _stato(client, struttura["id"])["istat"]
        assert istat["stato"] == "configurata"
        assert istat["parametri"]["tracciato"] == "ross1000-v2"
        assert istat["parametri"]["periodicita"] == "mensile"

    def test_regione_non_configurata_degrada_in_sicurezza(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(client)
        istat = _stato(client, struttura["id"])["istat"]

        assert istat["stato"] == "configurazione_non_disponibile"
        assert istat["motivo"] == "regione_non_configurata"
        assert istat["parametri"] is None

    def test_regione_non_riconosciuta_degrada_in_sicurezza(
        self, client: TestClient
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(client, regione="Terra di Mezzo")
        istat = _stato(client, struttura["id"])["istat"]

        assert istat["motivo"] == "regione_non_riconosciuta"
        assert istat["promemoria_manuale"] is True


class TestValiditaTemporale:
    def test_risoluzione_per_data_di_riferimento(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        # Delibera 2026: 2,00 € fino al 30/06; 3,00 € dal 01/07.
        _configura_comune(
            client, importo_cent=200, valido_dal="2026-01-01", valido_al="2026-06-30"
        )
        _configura_comune(client, importo_cent=300, valido_dal="2026-07-01")

        def importo(alla_data: str) -> int:
            return _stato(client, struttura["id"], alla_data=alla_data)[
                "tassa_soggiorno"
            ]["parametri"]["importo_cent"]

        assert importo("2026-03-15") == 200
        assert importo("2026-09-15") == 300

    def test_prima_del_primo_periodo_degrada_in_sicurezza(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        _configura_comune(client, valido_dal="2026-01-01")

        tassa = _stato(client, struttura["id"], alla_data="2025-12-31")[
            "tassa_soggiorno"
        ]
        assert tassa["stato"] == "configurazione_non_disponibile"


class TestCambioComune:
    def test_cambiare_comune_ricarica_la_config_applicabile(
        self, client: TestClient, anagrafica: None
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        _configura_comune(client, COMUNE_A["codice_istat"], importo_cent=200)
        _configura_comune(client, COMUNE_B["codice_istat"], importo_cent=500)

        def importo() -> int:
            return _stato(client, struttura["id"])["tassa_soggiorno"]["parametri"][
                "importo_cent"
            ]

        assert importo() == 200
        client.patch(
            f"/api/v1/strutture/{struttura['id']}",
            json={
                "comune": COMUNE_B["nome"],
                "comune_codice_istat": COMUNE_B["codice_istat"],
            },
        )
        assert importo() == 500

    def test_la_config_non_e_mai_copiata_sulla_struttura(
        self, client: TestClient, anagrafica: None
    ) -> None:
        # Invariante che protegge lo storico dei versamenti (FR-2): la
        # configurazione si risolve alla lettura da (comune, data), non si
        # materializza sulla Struttura.
        from app.strutture.models import Struttura

        colonne = {c.name for c in Struttura.__table__.columns}
        assert not [c for c in colonne if "tassa" in c or "aliquota" in c]

    def test_lo_storico_delle_config_sopravvive_al_cambio(
        self, client: TestClient, anagrafica: None, db_session: Session
    ) -> None:
        _accedi(client)
        struttura = _crea_struttura(
            client, comune_codice_istat=COMUNE_A["codice_istat"]
        )
        _configura_comune(client, COMUNE_A["codice_istat"], importo_cent=200)
        _configura_comune(client, COMUNE_B["codice_istat"], importo_cent=500)

        client.patch(
            f"/api/v1/strutture/{struttura['id']}",
            json={
                "comune": COMUNE_B["nome"],
                "comune_codice_istat": COMUNE_B["codice_istat"],
            },
        )
        # Le configurazioni del Comune precedente restano interrogabili:
        # i versamenti già registrati (Story 3.6) resteranno leggibili.
        vecchie = db_session.scalars(
            select(ComuneConfig).where(
                ComuneConfig.comune_codice_istat == COMUNE_A["codice_istat"]
            )
        ).all()
        assert [c.tassa_importo_cent for c in vecchie] == [200]


class TestEndpointInterniAuditati:
    def test_senza_token_admin_e_403(
        self, client: TestClient, anagrafica: None
    ) -> None:
        risposta = client.put(
            f"/api/v1/interno/comuni/{COMUNE_A['codice_istat']}/configurazione",
            json={
                "attore": "ignoto",
                "tassa_importo_cent": 100,
                "tassa_periodicita": "annuale",
                "valido_dal": "2026-01-01",
            },
        )
        assert risposta.status_code == 403
        assert risposta.headers["content-type"].startswith(PROBLEM)

    def test_token_errato_e_403(self, client: TestClient, anagrafica: None) -> None:
        risposta = client.put(
            f"/api/v1/interno/comuni/{COMUNE_A['codice_istat']}/configurazione",
            headers={"X-Admin-Token": "token-sbagliato"},
            json={
                "attore": "ignoto",
                "tassa_importo_cent": 100,
                "tassa_periodicita": "annuale",
                "valido_dal": "2026-01-01",
            },
        )
        assert risposta.status_code == 403

    def test_comune_sconosciuto_e_404(self, client: TestClient) -> None:
        assert _configura_comune(client, "Z99999").status_code == 404

    def test_ogni_aggiornamento_scrive_un_record_di_audit(
        self, client: TestClient, anagrafica: None, db_session: Session
    ) -> None:
        _configura_comune(client, importo_cent=200, attore="fahad@example.com")

        audit = db_session.scalars(select(ConfigAudit)).all()
        assert len(audit) == 1
        assert audit[0].attore == "fahad@example.com"  # chi
        assert audit[0].entita == "comune_config"  # cosa
        assert audit[0].entita_riferimento == COMUNE_A["codice_istat"]
        assert audit[0].creato_il is not None  # quando
        assert audit[0].dati["tassa_importo_cent"] == 200

    def test_aggiornare_le_aliquote_e_un_operazione_dati(
        self, client: TestClient, anagrafica: None, db_session: Session
    ) -> None:
        # NFR-4: cambiare un'aliquota non richiede un rilascio di codice.
        _configura_comune(client, importo_cent=200, valido_dal="2026-01-01")
        _configura_comune(client, importo_cent=350, valido_dal="2026-08-01")

        config = db_session.scalars(
            select(ComuneConfig).order_by(ComuneConfig.valido_dal)
        ).all()
        assert [c.tassa_importo_cent for c in config] == [200, 350]
        # La prima configurazione resta nello storico: viene chiusa, non
        # sovrascritta (append-only sulla validità temporale).
        assert config[0].valido_al == date(2026, 7, 31)
