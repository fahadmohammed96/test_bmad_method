"""Service di `config_normativa` (AD-9, NFR-4).

Due responsabilità:
1. risolvere la configurazione applicabile a una Struttura a una certa
   data — con **degrado sicuro**: se manca, lo stato è esplicito e non
   si inventa mai un default;
2. aggiornare la configurazione come operazione DATI, auditata
   (chi/cosa/quando), con validità temporale append-only.
"""

import enum
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config_normativa.models import (
    ComuneConfig,
    ConfigAudit,
    Periodicita,
    RegioneConfig,
)
from app.config_normativa.repository import AnagraficaRepository, ConfigRepository


class StatoConfigurazione(enum.Enum):
    CONFIGURATA = "configurata"
    NON_DISPONIBILE = "configurazione_non_disponibile"


class Motivo(enum.Enum):
    COMUNE_NON_RICONOSCIUTO = "comune_non_riconosciuto"
    COMUNE_NON_CONFIGURATO = "comune_non_configurato"
    REGIONE_NON_RICONOSCIUTA = "regione_non_riconosciuta"
    REGIONE_NON_CONFIGURATA = "regione_non_configurata"


# Copy di stato: tono informativo, mai di colpa (UX §5.1). Il Comune non
# configurato è una cosa che manca a NOI, non un errore dell'Host.
MESSAGGI = {
    Motivo.COMUNE_NON_RICONOSCIUTO: (
        "Non abbiamo ancora questo Comune in anagrafica: la Tassa di soggiorno "
        "non è ancora configurata per te. Ti ricorderemo di gestirla a mano."
    ),
    Motivo.COMUNE_NON_CONFIGURATO: (
        "La Tassa di soggiorno non è ancora configurata per il tuo Comune. "
        "Ti ricorderemo di gestirla a mano finché non lo sarà."
    ),
    Motivo.REGIONE_NON_RICONOSCIUTA: (
        "Non abbiamo ancora questa Regione in anagrafica: la rilevazione ISTAT "
        "non è ancora configurata per te. Ti ricorderemo di gestirla a mano."
    ),
    Motivo.REGIONE_NON_CONFIGURATA: (
        "La rilevazione ISTAT non è ancora configurata per la tua Regione. "
        "Ti ricorderemo di gestirla a mano finché non lo sarà."
    ),
}

MESSAGGIO_CONFIGURATA = "Configurazione disponibile e aggiornata."


class ComuneSconosciutoError(Exception):
    pass


class RegioneSconosciutaError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class ParametriTassa:
    importo_cent: int
    periodicita: Periodicita
    esenzione_eta_max: int | None
    esenzione_notti_oltre: int | None


@dataclass(frozen=True, slots=True)
class ParametriIstat:
    tracciato: str
    periodicita: Periodicita


@dataclass(frozen=True, slots=True)
class AreaConfigurazione:
    stato: StatoConfigurazione
    motivo: Motivo | None
    messaggio: str
    promemoria_manuale: bool
    parametri: ParametriTassa | ParametriIstat | None


def _non_disponibile(motivo: Motivo) -> AreaConfigurazione:
    return AreaConfigurazione(
        stato=StatoConfigurazione.NON_DISPONIBILE,
        motivo=motivo,
        messaggio=MESSAGGI[motivo],
        promemoria_manuale=True,
        parametri=None,
    )


def _configurata(parametri: ParametriTassa | ParametriIstat) -> AreaConfigurazione:
    return AreaConfigurazione(
        stato=StatoConfigurazione.CONFIGURATA,
        motivo=None,
        messaggio=MESSAGGIO_CONFIGURATA,
        promemoria_manuale=False,
        parametri=parametri,
    )


def risolvi_tassa(
    db: Session, comune_codice_istat: str | None, alla_data: date
) -> AreaConfigurazione:
    if comune_codice_istat is None:
        return _non_disponibile(Motivo.COMUNE_NON_RICONOSCIUTO)
    config = ConfigRepository(db).comune_config_vigente(comune_codice_istat, alla_data)
    if config is None:
        return _non_disponibile(Motivo.COMUNE_NON_CONFIGURATO)
    return _configurata(
        ParametriTassa(
            importo_cent=config.tassa_importo_cent,
            periodicita=config.tassa_periodicita,
            esenzione_eta_max=config.esenzione_eta_max,
            esenzione_notti_oltre=config.esenzione_notti_oltre,
        )
    )


def risolvi_istat(
    db: Session, regione_codice_istat: str | None, alla_data: date
) -> AreaConfigurazione:
    if regione_codice_istat is None:
        return _non_disponibile(Motivo.REGIONE_NON_RICONOSCIUTA)
    config = ConfigRepository(db).regione_config_vigente(
        regione_codice_istat, alla_data
    )
    if config is None:
        return _non_disponibile(Motivo.REGIONE_NON_CONFIGURATA)
    return _configurata(
        ParametriIstat(
            tracciato=config.istat_tracciato, periodicita=config.istat_periodicita
        )
    )


def _audita(
    db: Session, attore: str, entita: str, riferimento: str, dati: dict
) -> None:
    db.add(
        ConfigAudit(
            attore=attore, entita=entita, entita_riferimento=riferimento, dati=dati
        )
    )


def aggiorna_comune_config(
    db: Session,
    comune_codice_istat: str,
    *,
    attore: str,
    tassa_importo_cent: int,
    tassa_periodicita: Periodicita,
    valido_dal: date,
    valido_al: date | None = None,
    esenzione_eta_max: int | None = None,
    esenzione_notti_oltre: int | None = None,
) -> ComuneConfig:
    anagrafica = AnagraficaRepository(db)
    if anagrafica.comune_by_codice(comune_codice_istat) is None:
        raise ComuneSconosciutoError(comune_codice_istat)

    config_repo = ConfigRepository(db)
    # Una nuova delibera chiude il periodo precedente: lo storico resta.
    for aperta in config_repo.comune_config_aperte_dal(comune_codice_istat, valido_dal):
        aperta.valido_al = valido_dal - timedelta(days=1)

    config = ComuneConfig(
        comune_codice_istat=comune_codice_istat,
        tassa_importo_cent=tassa_importo_cent,
        tassa_periodicita=tassa_periodicita,
        esenzione_eta_max=esenzione_eta_max,
        esenzione_notti_oltre=esenzione_notti_oltre,
        valido_dal=valido_dal,
        valido_al=valido_al,
    )
    db.add(config)
    _audita(
        db,
        attore,
        "comune_config",
        comune_codice_istat,
        {
            "tassa_importo_cent": tassa_importo_cent,
            "tassa_periodicita": tassa_periodicita.value,
            "esenzione_eta_max": esenzione_eta_max,
            "esenzione_notti_oltre": esenzione_notti_oltre,
            "valido_dal": valido_dal.isoformat(),
            "valido_al": valido_al.isoformat() if valido_al else None,
        },
    )
    db.commit()
    return config


def aggiorna_regione_config(
    db: Session,
    regione_codice_istat: str,
    *,
    attore: str,
    istat_tracciato: str,
    istat_periodicita: Periodicita,
    valido_dal: date,
    valido_al: date | None = None,
) -> RegioneConfig:
    anagrafica = AnagraficaRepository(db)
    if anagrafica.regione_by_codice(regione_codice_istat) is None:
        raise RegioneSconosciutaError(regione_codice_istat)

    config_repo = ConfigRepository(db)
    for aperta in config_repo.regione_config_aperte_dal(
        regione_codice_istat, valido_dal
    ):
        aperta.valido_al = valido_dal - timedelta(days=1)

    config = RegioneConfig(
        regione_codice_istat=regione_codice_istat,
        istat_tracciato=istat_tracciato,
        istat_periodicita=istat_periodicita,
        valido_dal=valido_dal,
        valido_al=valido_al,
    )
    db.add(config)
    _audita(
        db,
        attore,
        "regione_config",
        regione_codice_istat,
        {
            "istat_tracciato": istat_tracciato,
            "istat_periodicita": istat_periodicita.value,
            "valido_dal": valido_dal.isoformat(),
            "valido_al": valido_al.isoformat() if valido_al else None,
        },
    )
    db.commit()
    return config
