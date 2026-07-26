"""Schemi API di `calendario` (AD-14).

Lo stato di sincronizzazione è **derivato** dal `sync_run` alla lettura, non
mantenuto come colonna: un timestamp duplicato è un timestamp che prima o poi
avanza su un run fallito, che è esattamente la falsa sincronia vietata da
NFR-2. I valori derivati arrivano dall'API e il frontend li presenta, mai li
ricalcola (AD-14).

L'URL torna al client **redatto**: se l'Host ha incollato un URL con
credenziali, quelle non si riflettono in nessuna risposta (NFR-17).
"""

import enum
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.calendario.models import CanaleFeed, CategoriaErroreSync, StatoPrenotazione


class StatoSincronizzazione(enum.Enum):
    """Cosa dire all'Host, compreso il caso «non lo so ancora».

    `MAI_SINCRONIZZATO` esiste perché il silenzio ambiguo è il modo in cui la
    falsa sincronia fa il danno maggiore: il sistema dice «non so» invece di
    lasciar credere che i dati siano aggiornati.
    """

    MAI_SINCRONIZZATO = "mai_sincronizzato"
    IN_CORSO = "in_corso"
    RIUSCITO = "riuscito"
    FALLITO = "fallito"


class FeedIcalInput(BaseModel):
    struttura_id: uuid.UUID
    url: str = Field(min_length=1, max_length=2000)
    canale: CanaleFeed = CanaleFeed.ALTRO


class FeedIcalOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    struttura_id: uuid.UUID
    url: str
    canale: CanaleFeed
    collegato_il: datetime
    stato_sync: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    ultimo_tentativo_il: datetime | None
    categoria_errore: CategoriaErroreSync | None
    # Quanti sync sono falliti di fila dall'ultimo riuscito (AR-10, NFR-1).
    # Distingue «un tentativo andato male», che capita, da «questo Feed ha
    # smesso di funzionare», che richiede una mossa dell'Host — senza, i due
    # casi arrivano alla stessa superficie con lo stesso aspetto.
    fallimenti_consecutivi: int
    prenotazioni_attive: int
    prenotazioni_rimosse_dal_feed: int
    eventi_malformati: int
    eventi_ricorrenti_non_espansi: int


class PrenotazioneOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    struttura_id: uuid.UUID
    canale: CanaleFeed
    ical_uid: str | None
    check_in: date
    check_out: date
    notti: int
    sommario: str | None
    stato: StatoPrenotazione


class PrenotazioniDelFeedOutput(BaseModel):
    """Prenotazioni di un Feed **con** la loro verità temporale (NFR-2, UX-DR6).

    Un envelope e non una lista nuda. UX-DR6 chiede l'etichetta «dati
    aggiornati alle HH:MM» su OGNI superficie che mostra dati da Feed, e una
    lista nuda di Prenotazioni non ha un posto dove metterla: il consumatore
    dovrebbe procurarsi il timestamp da una seconda chiamata e correlarlo a
    mano, cioè avrebbe due letture che possono divergere e nessuna che dica
    quale delle due vale.

    `stato_sync` viaggia insieme per la stessa ragione: senza, un Feed mai
    sincronizzato e uno sincronizzato senza prenotazioni arrivano entrambi
    come lista vuota e timestamp nullo — e sono affermazioni diverse.
    """

    model_config = ConfigDict(from_attributes=True)

    stato_sync: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    prenotazioni: list[PrenotazioneOutput]
