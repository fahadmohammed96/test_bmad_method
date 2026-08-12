"""Configurazione 12-factor: env vars per l'infrastruttura (spine Consistency).

I parametri normativi NON vivono qui: stanno nelle tabelle `config_normativa`
(AD-9). I segreti vivono nel secret manager dell'ambiente; `.env.example`
è il contratto.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HOSTPILOT_", env_file=".env", extra="ignore"
    )

    env: str = "dev"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/hostpilot"
    )
    worker_poll_seconds: float = 1.0

    # Sessione server-side (AD-15). `Secure` resta attivo ovunque; l'override
    # a False è ammesso SOLO in dev locale su http (browser senza TLS).
    session_cookie_name: str = "hostpilot_session"
    session_cookie_secure: bool = True
    session_ttl_days: int = 30

    # Origin del frontend ammessa dal CORS (cookie con credentials, AD-14/15).
    frontend_origin: str = "http://localhost:3000"

    # Freno ai tentativi di login (G-5): finestra temporale, mai lockout
    # permanente. Due limiti complementari: per account (Host preso di
    # mira) e per origine (spraying su molti account).
    login_max_tentativi_account: int = 5
    login_max_tentativi_origine: int = 20
    # `gt=0` come sui parametri di retention: una finestra di 0 minuti
    # scioglie il freno (nessun tentativo cade mai dentro l'intervallo) e,
    # moltiplicata in `identity/jobs.py`, taglierebbe le tracce nell'istante
    # in cui nascono. Un parametro assurdo deve fermare l'avvio.
    login_finestra_minuti: int = Field(default=15, gt=0)

    # Ogni quanto gira il purge delle sessioni scadute (job durevole).
    # `gt=0`: un intervallo di 0 minuti riaccoda il purge già scaduto e il
    # worker gira in ciclo stretto, consumando la coda di tutti i tenant.
    purge_sessioni_intervallo_minuti: int = Field(default=60, gt=0)

    # Retention della coda `job` (MYL-51). Dalla Story 2.2 `job` è una tabella
    # a crescita ILLIMITATA e a ritmo noto — ~96 righe per Feed al giorno col
    # poller a 15 minuti, più i cicli periodici di manutenzione — e nessuna
    # riga veniva mai eliminata: l'ironia che la proposta segnala è che il job
    # che pulisce le *sessioni* scadute esisteva e quello che pulisce i *job*
    # no. Impatto immediato nullo, degrado silenzioso a regime.
    #
    # Finestra CONFIGURABILE e non costante di codice (stessa disciplina di
    # AD-9): quanta storia della coda tenere è una scelta operativa — chi
    # diagnostica un incidente vuole più giorni, chi ha poco disco ne vuole
    # meno — e cambiarla non deve richiedere un rilascio.
    #
    # `gt=0` su entrambi, e qui e non solo nel codice che li consuma: una
    # finestra di 0 giorni cancellerebbe i job appena completati, e un
    # intervallo di 0 minuti riaccoderebbe il purge già scaduto consumando la
    # coda di tutti i tenant. Un parametro assurdo deve fermare l'avvio.
    job_retention_giorni: int = Field(default=30, gt=0)
    job_retention_intervallo_minuti: int = Field(default=60, gt=0)

    # Token degli endpoint interni di configurazione normativa (AD-9).
    # Vive nel secret manager dell'ambiente; se vuoto, gli endpoint sono
    # chiusi (nessun accesso di default).
    admin_token: str = ""

    # Cap di prodotto del pilota (FR-1): max Strutture ATTIVE per Host.
    # Parametro DISTINTO dalla soglia fiscale, che vive in config_normativa
    # (AD-12) e arriva con la Story 1.6.
    max_strutture_attive: int = 3

    # Politica di uscita di rete verso i Feed iCal (NFR-17, NFR-4): sono
    # CONFIGURAZIONE, non costanti di codice — un feed lento o enorme si
    # tara sull'ambiente senza toccare il codice.
    feed_timeout_connessione_secondi: float = 5.0
    feed_timeout_lettura_secondi: float = 10.0
    feed_dimensione_massima_byte: int = 5 * 1024 * 1024
    feed_max_redirect: int = 3
    # Tetto sull'INTERO fetch, redirect compresi. I timeout sopra sono
    # per-operazione: un portale che sgocciola un byte appena dentro il
    # timeout di lettura non ne farebbe scattare nessuno, e il worker è un
    # ciclo sequenziale in-process — la connessione appesa fermerebbe i job
    # di tutti gli Host, non solo di quello del Feed lento.
    feed_deadline_totale_secondi: float = 30.0
    # Reti normalmente VIETATE (loopback, private, link-local) da ammettere
    # comunque, in CIDR separati da virgola. Vuoto in ogni ambiente reale:
    # esiste per i test, che parlano con un server HTTP su 127.0.0.1, e per
    # un'installazione self-hosted con il portale in rete locale. Il default
    # vuoto è sorvegliato da un test: la denylist non si allenta per svista.
    feed_reti_consentite: str = ""

    # Poller periodico dei Feed (AD-10, G3-5, NFR-4). Il default di 15 minuti
    # e la riduzione a 5 «in prossimità di un check-in» sono parametri
    # operativi tarabili coi dati del pilota, non costanti di codice: un
    # intervallo hardcoded renderebbe «configurabile» una parola del
    # documento invece di una proprietà del sistema.
    feed_sync_intervallo_minuti: int = 15
    feed_sync_intervallo_minimo_minuti: int = 5
    # Quanto prima di un check-in l'intervallo scende al minimo. «In
    # prossimità» non è quantificato in `epics.md` (test design §4.2-8):
    # questo è il parametro proposto DAL test design, non
    # un'interpretazione scelta qui — l'AC resta tracciato come non
    # chiudibile finché la decisione di prodotto non arriva.
    feed_sync_finestra_prossimita_ore: int = 24
    # Dopo quanti fallimenti CONSECUTIVI il Feed produce un alert interno
    # (AR-10, NFR-1). Mai hardcoded: la soglia giusta dipende
    # dall'intervallo, e i due parametri si tarano insieme.
    feed_sync_fallimenti_per_alert: int = 3

    # Retention dell'anagrafica Ospite (AD-21, NFR-12). Il PERIODO è un
    # parametro, mai una costante: il valore qui è **provvisorio** in attesa
    # dell'esito di R-5, che deve qualificare la base giuridica dei contatti
    # — dati personali di TERZI, non del cliente. 90 giorni è il valore
    # proposto nel Deferred dello spine, dello stesso ordine del bound M di
    # G2-D. Alla scadenza si azzerano i campi, mai si cancella una riga.
    #
    # La DECORRENZA non è qui e non è configurabile: vive in AD-21
    # (`check_out`, o l'uscita da `attiva` se precedente) ed è implementata
    # in `app/calendario/retention.py`.
    #
    # `gt=0` sui due parametri, e non solo nel codice che li consuma: un
    # `HOSTPILOT_OSPITE_RETENTION_GIORNI=0` azzererebbe i contatti della
    # Prenotazione in corso, e un intervallo di 0 minuti riaccoderebbe il job
    # già scaduto consumando la coda di tutti i tenant. `retention.py`
    # dichiara che un parametro sbagliato «deve fermare l'avvio»: la
    # validazione va dove l'avvio la incontra, cioè qui, altrimenti
    # `import app.main` riesce e il difetto si manifesta a regime.
    # Canale email delle notifiche (AD-13, Story 2.6). Sono INFRASTRUTTURA —
    # dove sta il relay, con che mittente si firma — quindi vivono qui e non
    # in `config_normativa` (AD-9), che ospita i parametri normativi.
    #
    # Default VUOTI e nessun fallback: senza SMTP configurato il canale
    # fallisce in modo esplicito e il job resta ritentabile, poi `failed` col
    # motivo. Un default inventato (`localhost:25`) produrrebbe notifiche
    # dichiarate inviate e mai partite, che è il difetto di severità alta di
    # NFR-3 nella sua forma peggiore, perché silenziosa.
    smtp_host: str = ""
    smtp_porta: int = 587
    smtp_mittente: str = ""
    # `gt=0`: un timeout di 0 secondi non è «senza limite», è una connessione
    # che non può riuscire — e un parametro assurdo deve fermare l'avvio.
    smtp_timeout_secondi: float = Field(default=10.0, gt=0)

    ospite_retention_giorni: int = Field(default=90, gt=0)
    # Ogni quanto gira il job di azzeramento. Distinto dal periodo: è la
    # granularità con cui si esegue l'adempimento, non la sua scadenza.
    ospite_retention_intervallo_minuti: int = Field(default=60, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()
