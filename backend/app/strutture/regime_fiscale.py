"""Regime fiscale derivato (FR-17, AD-12).

Il Regime NON è uno stato: è una funzione del numero di Strutture non
archiviate dell'Host, valutata al momento della lettura. Non esiste una
colonna che possa divergere dal conteggio.

Soglia, regimi, testi e aliquote citate vivono in `config_normativa`:
qui non c'è nessuna costante normativa. Il contenuto è informativo con
disclaimer — mai un calcolo d'imposta (Non-Goal PRD §8).
"""

import enum
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.config_normativa import service as config_service
from app.config_normativa.models import ParametroFiscale
from app.strutture.repository import StrutturaRepository

DISCLAIMER = (
    "Informazione di orientamento, non una consulenza fiscale: "
    "verifica sempre la tua situazione con un commercialista."
)


class StatoRegime(enum.Enum):
    DISPONIBILE = "disponibile"
    NON_DISPONIBILE = "configurazione_non_disponibile"


MESSAGGIO_NON_DISPONIBILE = (
    "I parametri fiscali non sono ancora configurati: non possiamo "
    "indicarti il regime applicabile. Ti conviene chiedere al tuo "
    "commercialista."
)


@dataclass(frozen=True, slots=True)
class RegimeFiscale:
    stato: StatoRegime
    strutture_non_archiviate: int
    soglia: int | None
    oltre_soglia: bool
    regime: str | None
    testo: str
    aliquote_citate: str | None
    disclaimer: str
    mostra_pannello_transizione: bool


def _senza_parametri(conteggio: int) -> RegimeFiscale:
    return RegimeFiscale(
        stato=StatoRegime.NON_DISPONIBILE,
        strutture_non_archiviate=conteggio,
        soglia=None,
        oltre_soglia=False,
        regime=None,
        testo=MESSAGGIO_NON_DISPONIBILE,
        aliquote_citate=None,
        disclaimer=DISCLAIMER,
        mostra_pannello_transizione=False,
    )


def oltre_soglia(conteggio: int, parametri: ParametroFiscale) -> bool:
    """Unico punto in cui si decide se la soglia normativa è superata."""
    return conteggio >= parametri.soglia_strutture


def calcola_regime(
    db: Session,
    host_id: uuid.UUID,
    *,
    alla_data: date,
    lettura_confermata: bool,
) -> RegimeFiscale:
    conteggio = StrutturaRepository(db).conta_attive(host_id)
    parametri = config_service.parametri_fiscali_vigenti(db, alla_data)
    if parametri is None:
        return _senza_parametri(conteggio)

    superata = oltre_soglia(conteggio, parametri)
    return RegimeFiscale(
        stato=StatoRegime.DISPONIBILE,
        strutture_non_archiviate=conteggio,
        soglia=parametri.soglia_strutture,
        oltre_soglia=superata,
        regime=(
            parametri.regime_da_soglia if superata else parametri.regime_sotto_soglia
        ),
        testo=(parametri.testo_da_soglia if superata else parametri.testo_sotto_soglia),
        aliquote_citate=parametri.aliquote_citate,
        disclaimer=DISCLAIMER,
        # Pannello a schermo intero finché l'Host non conferma di averlo
        # letto (UX-DR14). Sotto soglia non si mostra mai — nessuna
        # notifica residua — e il rientro azzera la conferma, così una
        # nuova risalita lo ripropone (UJ-4 edge).
        mostra_pannello_transizione=superata and not lettura_confermata,
    )
