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
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.calendario.models import (
    AmbitoAzzeramento,
    CanaleFeed,
    CategoriaErroreSync,
    StatoPrenotazione,
)


def _niente_se_vuoto(valore: object) -> object:
    """Stringa vuota o di soli spazi ⇒ `None`, cioè «non indicato».

    Serve perché un form HTML invia **sempre** i suoi campi: i campi che l'Host
    non ha toccato arrivano come `""`. Senza questa normalizzazione un
    `nome = ""` finirebbe nell'anagrafica — un valore che non è un valore, che
    in griglia è indistinguibile da un nome mancante e che la retention
    dovrebbe poi «azzerare» pur essendo già vuoto. E su `email` la stringa
    vuota non passerebbe nemmeno la validazione del formato, trasformando un
    campo facoltativo in un 422: cioè esattamente il modo in cui un campo
    dichiarato facoltativo diventa obbligatorio nei fatti.
    """
    if isinstance(valore, str):
        pulito = valore.strip()
        return pulito or None
    return valore


# Testo facoltativo dell'Host: assente, oppure con del contenuto. Mai vuoto.
TestoFacoltativo = Annotated[str | None, BeforeValidator(_niente_se_vuoto)]
EmailFacoltativa = Annotated[EmailStr | None, BeforeValidator(_niente_se_vuoto)]


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

    @field_validator("canale")
    @classmethod
    def _un_feed_non_e_un_inserimento_manuale(cls, valore: CanaleFeed) -> CanaleFeed:
        """`manuale` è un Canale del Glossario, non un portale da cui leggere.

        Il rifiuto sta qui, all'ingresso, e non solo nel CHECK della tabella:
        un Feed dichiarato `manuale` supererebbe il collegamento e le sue
        Prenotazioni verrebbero rifiutate dal database **al primo sync**, cioè
        come un 500 dentro un job — un fallimento lontano dalla causa e
        invisibile all'Host, invece di un errore inline sul campo (FR-3).
        """
        if valore is CanaleFeed.MANUALE:
            raise ValueError(
                "«manuale» è il Canale di una Prenotazione inserita a mano, "
                "non di un calendario da importare"
            )
        return valore


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


class StrutturaDelCalendarioOutput(BaseModel):
    """Le Strutture del perimetro, per etichettare le righe della griglia.

    Viaggiano dentro la risposta del Calendario e non da una seconda
    chiamata: la griglia aggrega più Strutture (FR-4) e senza i nomi
    mostrerebbe degli UUID, oppure il client dovrebbe correlare a mano due
    letture che possono divergere.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str


class VoceCalendarioOutput(BaseModel):
    """Una Prenotazione come la griglia la mostra (FR-4).

    Porta Canale d'origine, Struttura, date **e Ospite**. Tre valori sono
    derivati dal server e il frontend li presenta senza ricalcolarli
    (AD-14): `notti`, che è la lunghezza dell'intervallo semiaperto
    `[check_in, check_out)` di AD-3; `ospite_principale`, che è la scelta
    fra più Ospiti registrati; `altri_ospiti`, il loro conteggio.

    `ospite_principale` è `None` quando l'Ospite non è noto — e non è un
    errore: una Prenotazione senza Ospite resta valida, e la superficie
    scrive «Ospite non indicato», mai un segnaposto che somigli a un nome
    (NFR-11, AD-21).

    `sommario` resta il testo OPACO del portale, dove il portale l'ha
    scritto: non è il nome dell'Ospite e non lo diventa passando di qui.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    struttura_id: uuid.UUID
    canale: CanaleFeed
    check_in: date
    check_out: date
    notti: int
    sommario: str | None
    stato: StatoPrenotazione
    ospite_principale: str | None
    altri_ospiti: int


class CalendarioOutput(BaseModel):
    """La griglia unificata: Prenotazioni di tutte le Strutture e i Canali.

    Envelope, e per la ragione di sempre: UX-DR6 vuole «dati aggiornati
    alle HH:MM» su ogni superficie che mostra dati da Feed, e questa li
    mostra da PIÙ Feed insieme.

    `ultimo_sync_riuscito_il` è il **meno recente** fra i Feed del
    perimetro, non il più recente: la freschezza di una vista aggregata è
    quella della sua fonte più vecchia. Prendere il massimo direbbe
    all'Host che il calendario è aggiornato a due minuti fa mentre uno dei
    due portali non risponde da tre giorni — la falsa sincronia di NFR-2
    con l'aggravante di essere aritmeticamente vera.

    È `None` appena un Feed del perimetro non ha MAI avuto un sync
    riuscito: lì non esiste un orario da mostrare, e il sistema dice «non
    lo so» invece di mostrarne uno che parla solo degli altri Feed.

    I tre conteggi esistono perché «nessun Feed collegato», «un Feed che
    non ha mai importato» e «un Feed in errore» arrivano altrimenti alla
    superficie con lo stesso aspetto — timestamp assente — e sono
    affermazioni diverse.
    """

    model_config = ConfigDict(from_attributes=True)

    da: date
    a: date
    stato_sync: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    feed_collegati: int
    feed_mai_sincronizzati: int
    feed_in_errore: int
    strutture: list[StrutturaDelCalendarioOutput]
    voci: list[VoceCalendarioOutput]


class OspiteInput(BaseModel):
    """L'Ospite che l'Host **può** — non deve — indicare (NFR-11, AD-21).

    Tre campi, **tutti facoltativi**, nessuno con un valore di default che non
    sia «assente». Non esiste un ordine in cui compilarli, non ce n'è uno
    obbligatorio se ne dai un altro, e nessuno viene dedotto da qualcos'altro:
    in particolare il `sommario` della Prenotazione **non** è un suggerimento
    di `nome`, nemmeno come valore iniziale del form
    (`[DECISIONE MYL-40]` → PRD §14.2).

    Se tutti e tre restano vuoti non nasce alcuna riga `ospite`: «blocco date»
    è un caso normale, non un inserimento incompleto.

    Nessun campo di documento d'identità: quelli vivono solo in
    `ospite_documento` (Epic 3, AD-11), con cifratura e retention proprie.
    """

    nome: TestoFacoltativo = Field(default=None, max_length=200)
    # `EmailStr` e non una stringa qualsiasi: il contatto serve a scrivere
    # all'Ospite (Epic 5), e un indirizzo malformato è un messaggio che non
    # partirà — meglio un errore inline adesso che un invio fallito allora.
    # La stringa vuota è normalizzata a `None` PRIMA della validazione, quindi
    # il campo resta facoltativo davvero.
    email: EmailFacoltativa = Field(default=None, max_length=320)
    telefono: TestoFacoltativo = Field(default=None, max_length=50)


class PrenotazioneManualeInput(BaseModel):
    """Ciò che l'Host scrive per inserire una Prenotazione a mano (FR-7).

    Tre campi obbligatori — la Struttura e le due date — e nient'altro. Il
    Canale non si dichiara: una Prenotazione scritta qui è `manuale` per
    definizione (Glossario PRD §4), e accettarlo dal client permetterebbe di
    registrare una prenotazione «da Airbnb» che Airbnb non conosce.

    `sommario` è la nota con cui l'Host riconosce la Prenotazione — «blocco per
    manutenzione», il nome di chi ha chiamato — e resta testo **opaco**: non
    diventa il nome dell'Ospite passando di qui, ed è un campo diverso proprio
    perché è una cosa diversa (NFR-11).
    """

    struttura_id: uuid.UUID
    check_in: date
    check_out: date
    sommario: TestoFacoltativo = Field(default=None, max_length=500)
    ospite: OspiteInput | None = None


class PrenotazioneManualeOutput(BaseModel):
    """La Prenotazione manuale come il server la restituisce.

    `notti` è derivato qui e il client lo presenta (AD-14): il modo realistico
    in cui quell'invariante si perde è che il browser rifaccia il conto con la
    propria timezone, e i due risultati smettano di coincidere il giorno del
    cambio d'ora.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    struttura_id: uuid.UUID
    canale: CanaleFeed
    check_in: date
    check_out: date
    notti: int
    sommario: str | None
    stato: StatoPrenotazione
    ospite_principale: str | None


class AzzeramentoInput(BaseModel):
    """Chi chiede l'azzeramento (NFR-15). Nient'altro.

    Solo l'attore, perché il «cosa» sta nel percorso e il «quando» lo decide
    il server: un payload che portasse un nome o un contatto scriverebbe un
    dato personale nel log della richiesta, cioè proprio ciò che
    l'azzeramento sta per togliere (AD-16, NFR-11).
    """

    attore: str = Field(min_length=1, max_length=200)


class AzzeramentoOutput(BaseModel):
    """L'evidenza, in conteggi e identificatori.

    I due conteggi sono distinti e non sommati: «un'anagrafica azzerata» e
    «un `sommario` azzerato» sono adempimenti diversi su tabelle diverse, e
    un totale unico nasconderebbe il caso in cui uno dei due non è avvenuto —
    che è esattamente il buco che questo lotto chiude.
    """

    ambito: AmbitoAzzeramento
    riferimento: uuid.UUID
    anagrafiche_azzerate: int
    sommari_azzerati: int
    eseguito_il: datetime
