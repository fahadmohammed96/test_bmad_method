"""Service di `calendario` (AD-4, AD-18, AD-19).

Due percorsi, deliberatamente separati nel tempo (test design §4.2-1):

- **`collega_feed` è sincrono e non tocca la rete.** Valida il formato
  dell'URL e accoda un job di sync scaduto subito. L'errore inline immediato
  sul campo può parlare solo di ciò che si sa senza uscire: uno schema
  inammissibile, un URL senza host.
- **`esegui_sync` è il job.** Qui si scopre la raggiungibilità, e l'esito
  arriva all'Host come stato del Feed entro il primo run.

L'invariante che governa tutto il resto (E2-G3): la transizione a
`rimossa_dal_feed` si applica **solo** dopo un parse completo e validato.
Un corpo troncato, vuoto o con esito HTTP inatteso produce un `sync_run`
fallito e **nessuna** transizione di stato. Senza questa regola un errore di
trasporto svuoterebbe logicamente il calendario, facendo `decadere` i
Conflitti aperti: probabilità alta, impatto critico, nessun errore visibile.

Nessuna funzione di questo modulo fa `commit` sul percorso del job: la
transazione è del chiamante. Il worker esegue ogni handler dentro un
SAVEPOINT (G-1) e un `commit` interno lo scavalcherebbe.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.calendario import azzeramento, ical, jobs
from app.calendario.intervallo import ParametriIntervallo, intervallo_di_sync
from app.calendario.models import (
    AmbitoAzzeramento,
    AzzeramentoAudit,
    CanaleFeed,
    CategoriaErroreSync,
    EsitoSyncRun,
    FeedIcal,
    Ospite,
    Prenotazione,
    StatoPrenotazione,
    SyncRun,
)
from app.calendario.normalizzazione import (
    EventoFeed,
    normalizza,
)
from app.calendario.repository import (
    AzzeramentoAuditRepository,
    FeedIcalRepository,
    OspiteRepository,
    PrenotazioneRepository,
    SyncRunRepository,
)
from app.calendario.schemas import StatoSincronizzazione
from app.calendario.trasporto import (
    ClientFeed,
    ClientFeedHttp,
    ErroreDiTrasporto,
    EsitoHttpInattesoError,
    RispostaFeed,
    RispostaTroppoGrandeError,
    TimeoutFeedError,
    Validatori,
)
from app.calendario.uscita_rete import (
    PoliticaUscitaRete,
    UrlFeedNonValidoError,
    url_redatto,
    valida_formato,
)
from app.core.config import get_settings
from app.core.date_range import DateRange, today_rome, utcnow
from app.core.outbox import emit
from app.identity import service as identity_service
from app.strutture import service as strutture_service

logger = logging.getLogger(__name__)

# AD-17: il nome è a catalogo in `core/events.py`, che ne valida anche il
# payload. La costante vive qui perché `calendario` è il modulo che emette
# l'evento, e un letterale ripetuto nel codice e nei test è un letterale che
# prima o poi diverge.
EVENTO_PRENOTAZIONE_CESSATA = "prenotazione.cessata"


class FeedNonTrovatoError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DatiFeed:
    struttura_id: uuid.UUID
    url: str
    canale: CanaleFeed


@dataclass(frozen=True, slots=True)
class StatoFeed:
    """Feed più il suo stato di sincronizzazione, derivato alla lettura."""

    feed: FeedIcal
    stato: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    ultimo_tentativo_il: datetime | None
    categoria_errore: CategoriaErroreSync | None
    # Quante volte di fila il sync è fallito dall'ultimo riuscito (AR-10).
    # È il segnale che distingue «un tentativo andato male» da «questo Feed
    # ha smesso di funzionare», e senza di esso l'Host li vede uguali.
    fallimenti_consecutivi: int
    prenotazioni_attive: int
    prenotazioni_rimosse_dal_feed: int
    eventi_malformati: int
    eventi_ricorrenti_non_espansi: int


@dataclass(frozen=True, slots=True)
class EsitoImport:
    """Contatori di un run, come finiscono nel `sync_run`."""

    importate: int = 0
    aggiornate: int = 0
    rimosse_dal_feed: int = 0
    ricomparse: int = 0
    malformati: int = 0
    ricorrenti_non_espansi: int = 0


def client_di_produzione() -> ClientFeed:
    """Confine di rete configurato dall'ambiente (NFR-4, NFR-17)."""
    return ClientFeedHttp(PoliticaUscitaRete.da_configurazione(get_settings()))


def collega_feed(db: Session, host_id: uuid.UUID, dati: DatiFeed) -> FeedIcal:
    """Collega il Feed e accoda subito il sync. Solleva `UrlFeedNonValidoError`.

    La Struttura si legge dal service di `strutture`, mai dal suo repository:
    `calendario` non conosce le tabelle di un altro modulo (AD-1, AD-18). E si
    legge **attiva**: collegare un Feed a una Struttura archiviata la
    riporterebbe a sincronizzare, che è l'opposto di ciò che archiviare vuol
    dire (AD-20).
    """
    strutture_service.leggi_struttura_attiva(db, host_id, dati.struttura_id)
    url = dati.url.strip()
    # Validazione SINCRONA di solo formato: nessun DNS, nessuna connessione.
    # L'errore inline immediato non può dipendere dalla rete.
    valida_formato(url)

    feed = FeedIcalRepository(db).add(
        host_id,
        FeedIcal(struttura_id=dati.struttura_id, url=url, canale=dati.canale),
    )
    db.flush()
    jobs.accoda_sync_immediato(db, feed)
    # Il ciclo periodico parte SUBITO col collegamento, non al prossimo
    # riavvio del worker: il bootstrap all'avvio è una rete di sicurezza, e
    # affidargli il primo giro significherebbe che un Feed collegato oggi
    # comincia a risincronizzarsi al prossimo rilascio (AD-10, NFR-1).
    jobs.assicura_sync_periodico(db, feed)
    db.commit()
    return feed


def lista_feed(
    db: Session, host_id: uuid.UUID, struttura_id: uuid.UUID
) -> list[FeedIcal]:
    strutture_service.leggi_struttura(db, host_id, struttura_id)
    return FeedIcalRepository(db).della_struttura(host_id, struttura_id)


def leggi_feed(db: Session, host_id: uuid.UUID, feed_id: uuid.UUID) -> FeedIcal:
    feed = FeedIcalRepository(db).by_id(host_id, feed_id)
    if feed is None:
        raise FeedNonTrovatoError()
    return feed


def ultimo_run(db: Session, host_id: uuid.UUID, feed_id: uuid.UUID) -> SyncRun | None:
    return SyncRunRepository(db).ultimo(host_id, feed_id)


def ultimo_run_riuscito(
    db: Session, host_id: uuid.UUID, feed_id: uuid.UUID
) -> SyncRun | None:
    """Sorgente unica di «dati aggiornati alle HH:MM» (NFR-2).

    Deriva dal `sync_run`, non da un campo mantenuto a parte: un timestamp
    duplicato è un timestamp che prima o poi avanza su un run fallito.
    """
    return SyncRunRepository(db).ultimo_riuscito(host_id, feed_id)


def intervallo_prossimo_sync(
    db: Session, host_id: uuid.UUID, feed: FeedIcal
) -> timedelta:
    """Quanto attendere prima del prossimo sync di questo Feed (G3-5).

    Lo stato (il prossimo check-in) si legge qui; la REGOLA sta in
    `intervallo.py` ed è pura. La separazione non è estetica: è ciò che
    permette di provare la regola su tutti i suoi confini senza un database e
    senza attendere quindici minuti.

    **Si cerca dal primo giorno NON ancora iniziato**, cioè da domani. Un
    check-in di oggi ha la propria mezzanotte alle spalle: l'ospite è già
    arrivato, e la finestra che l'intervallo stretto protegge è quella che
    *precede* l'arrivo. Cercando da oggi, il `LIMIT 1` restituiva proprio
    quel check-in passato e **oscurava quello di domani**, riportando
    l'intervallo al pieno — cioè l'AC 10 si invertiva nel giorno di massima
    occupazione, che è quello in cui una cancellazione tardiva non vista costa
    di più. La regola pura scarta comunque un arrivo passato, ma non può
    vedere quello che la query non le ha passato.
    """
    impostazioni = get_settings()
    prossimo = PrenotazioneRepository(db).prossimo_check_in(
        host_id,
        struttura_id=feed.struttura_id,
        da=today_rome() + timedelta(days=1),
    )
    return intervallo_di_sync(
        adesso=utcnow(),
        prossimo_check_in=prossimo,
        parametri=ParametriIntervallo(
            intervallo_minuti=impostazioni.feed_sync_intervallo_minuti,
            intervallo_minimo_minuti=impostazioni.feed_sync_intervallo_minimo_minuti,
            finestra_prossimita_ore=impostazioni.feed_sync_finestra_prossimita_ore,
        ),
    )


def prenotazioni_del_feed(
    db: Session, host_id: uuid.UUID, feed_id: uuid.UUID
) -> list[Prenotazione]:
    return PrenotazioneRepository(db).del_feed(host_id, feed_id)


def stato_del_feed(db: Session, host_id: uuid.UUID, feed: FeedIcal) -> StatoFeed:
    """Stato di sincronizzazione DERIVATO alla lettura (NFR-2, AD-14).

    Non esiste una colonna «ultimo sync riuscito» da tenere allineata: la
    verità è la traccia append-only dei `sync_run`, e qui si legge.
    """
    run = SyncRunRepository(db)
    ultimo = run.ultimo(host_id, feed.id)
    riuscito = run.ultimo_riuscito(host_id, feed.id)
    # Due domande diverse, e sarebbe un difetto confonderle. Il TIMESTAMP
    # viene dall'ultimo run riuscito, 304 compresi: un 304 è una verifica
    # riuscita e i dati mostrati sono correnti. I CONTEGGI di eventi non
    # importati vengono dall'ultima RICONCILIAZIONE: un run da 304 li ha a
    # zero perché non ha letto nulla, e derivarli da lì spegnerebbe l'avviso
    # proprio quando il portale conferma che gli eventi illeggibili ci sono
    # ancora tutti.
    riconciliato = run.ultimo_riconciliato(host_id, feed.id)
    conteggi = PrenotazioneRepository(db).conta_per_stato(host_id, feed.id)

    if ultimo is None:
        in_coda = FeedIcalRepository(db).sync_in_coda(
            host_id, feed.id, tipo_job=jobs.TIPO_JOB_SYNC_FEED
        )
        stato = (
            StatoSincronizzazione.IN_CORSO
            if in_coda
            else StatoSincronizzazione.MAI_SINCRONIZZATO
        )
    elif ultimo.esito is EsitoSyncRun.RIUSCITO:
        stato = StatoSincronizzazione.RIUSCITO
    else:
        stato = StatoSincronizzazione.FALLITO

    return StatoFeed(
        feed=feed,
        stato=stato,
        ultimo_sync_riuscito_il=None if riuscito is None else riuscito.concluso_il,
        ultimo_tentativo_il=None if ultimo is None else ultimo.concluso_il,
        categoria_errore=None if ultimo is None else ultimo.categoria_errore,
        fallimenti_consecutivi=run.fallimenti_consecutivi(host_id, feed.id),
        prenotazioni_attive=conteggi.get(StatoPrenotazione.ATTIVA, 0),
        prenotazioni_rimosse_dal_feed=conteggi.get(
            StatoPrenotazione.RIMOSSA_DAL_FEED, 0
        ),
        eventi_malformati=(
            0 if riconciliato is None else riconciliato.eventi_malformati
        ),
        eventi_ricorrenti_non_espansi=(
            0 if riconciliato is None else riconciliato.eventi_ricorrenti_non_espansi
        ),
    )


# ------------------------------------------------ anagrafica Ospite (AD-21)


class PrenotazioneNonTrovataError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DatiOspite:
    """Ciò che si può sapere di un Ospite, e nulla di più (AD-21, NFR-11).

    Tre campi, tutti facoltativi. Non esiste un costruttore che ne richieda
    uno, e non esiste un percorso che li ricavi da altro: `sommario` è
    testo opaco del portale e resta sulla Prenotazione. Se l'unica cosa che
    si sa è che c'è qualcuno, si registra un Ospite senza contatti — che è
    un'informazione, non un errore.

    Nessun campo di documento d'identità: quelli vivono solo in
    `ospite_documento` (Epic 3, AD-11), con cifratura e retention proprie.
    """

    nome: str | None = None
    email: str | None = None
    telefono: str | None = None
    principale: bool = False


def registra_ospite(
    db: Session,
    host_id: uuid.UUID,
    prenotazione_id: uuid.UUID,
    dati: DatiOspite,
) -> Ospite:
    """Scrive un Ospite sull'anagrafica. `calendario` è l'unico scrittore (AD-18).

    Non fa `commit`: la transazione è del chiamante, come ovunque sul
    percorso dei job. La Prenotazione si verifica prima, e con l'`host_id`
    della sessione: un Ospite appeso alla Prenotazione di un altro Host
    sarebbe una fuga scritta a mano (AD-2, NFR-14).
    """
    prenotazione = PrenotazioneRepository(db).by_id(host_id, prenotazione_id)
    if prenotazione is None:
        raise PrenotazioneNonTrovataError()
    return OspiteRepository(db).add(
        host_id,
        Ospite(
            prenotazione_id=prenotazione_id,
            nome=dati.nome,
            email=dati.email,
            telefono=dati.telefono,
            principale=dati.principale,
        ),
    )


def _ospite_da_registrare(dati: DatiOspite | None) -> DatiOspite | None:
    """L'Ospite da scrivere, oppure `None` perché non ce n'è uno.

    Tre campi vuoti **non** sono un Ospite. Una riga `ospite` con `nome`,
    `email` e `telefono` a `NULL` sarebbe indistinguibile da un'anagrafica
    azzerata dalla retention (AD-21) — l'evidenza `anonimizzato_il` esiste
    proprio per separare «non ha mai avuto contatti» da «i contatti sono stati
    cancellati», e scrivere righe vuote la renderebbe ambigua.

    È anche il caso reale: un form HTML invia **sempre** i suoi campi, e li
    invia come stringa vuota. Se questa funzione non esistesse, «l'Host non ha
    indicato nessun Ospite» arriverebbe come un Ospite con tre stringhe vuote —
    valori che non sono valori.
    """
    if dati is None:
        return None
    return dati if any((dati.nome, dati.email, dati.telefono)) else None


def ospiti_della_prenotazione(
    db: Session, host_id: uuid.UUID, prenotazione_id: uuid.UUID
) -> list[Ospite]:
    """Lettura dell'anagrafica per gli altri moduli (AD-18).

    Epic 3 (Alloggiati) ed Epic 5 (Messaggi) leggono da qui e mai dalle
    tabelle: è l'unico punto in cui la proprietà dell'entità resta
    verificabile invece di essere una raccomandazione.
    """
    return OspiteRepository(db).della_prenotazione(host_id, prenotazione_id)


# --------------------------------------- Prenotazioni manuali (FR-7, Story 2.4)


class PrenotazioneNonManualeError(Exception):
    """Lo stato di una Prenotazione da Feed lo decide il portale (AD-4)."""


@dataclass(frozen=True, slots=True)
class DatiPrenotazioneManuale:
    """Ciò che l'Host scrive di suo pugno (FR-7).

    `sommario` e `ospite` sono facoltativi e restano separati: il `sommario` è
    la nota della Prenotazione — testo **opaco**, per riconoscerla — e non è
    mai la sorgente di un nome di Ospite, nemmeno come suggerimento
    (NFR-11, `[DECISIONE MYL-40]` → PRD §14.2). Sono due campi perché sono due
    cose: «blocco per manutenzione» non è l'identità di nessuno.

    Il Canale non è un parametro: una Prenotazione scritta qui è `manuale` per
    definizione (Glossario PRD §4), e lasciarlo scegliere al client permetterebbe
    di dichiarare una prenotazione «da Airbnb» che Airbnb non conosce.
    """

    struttura_id: uuid.UUID
    check_in: date
    check_out: date
    sommario: str | None = None
    ospite: DatiOspite | None = None


def crea_prenotazione_manuale(
    db: Session, host_id: uuid.UUID, dati: DatiPrenotazioneManuale
) -> Prenotazione:
    """Crea una Prenotazione manuale in stato `attiva` (FR-7, AD-19).

    Solleva `EmptyDateRangeError` (intervallo vuoto),
    `StrutturaNonTrovataError` e `StrutturaArchiviataError`.

    **L'ordine dei tre passi è parte del comportamento.** Prima l'intervallo,
    che è puro e non tocca niente; poi la Struttura, letta dal service di
    `strutture` (AD-18) e letta ATTIVA (AD-20); solo dopo la scrittura. Così
    nessun percorso d'errore lascia una riga a metà, e la validazione più
    economica è anche la prima.

    La Prenotazione nasce `attiva` e con la stessa forma di una da Feed: è ciò
    che la rende indistinguibile agli occhi della rilevazione dei Conflitti
    (Story 2.5), che non esiste ancora e che non deve dover conoscere due
    sorgenti.
    """
    # `DateRange` è l'unica semantica temporale del prodotto (AD-3): il
    # confine `[check_in, check_out)` non si reimplementa qui, altrimenti il
    # turnover dello stesso giorno diventerebbe una sovrapposizione in un punto
    # e non nell'altro.
    soggiorno = DateRange(check_in=dati.check_in, check_out=dati.check_out)
    strutture_service.leggi_struttura_attiva(db, host_id, dati.struttura_id)

    prenotazione = PrenotazioneRepository(db).crea_manuale(
        host_id,
        struttura_id=dati.struttura_id,
        check_in=soggiorno.check_in,
        check_out=soggiorno.check_out,
        sommario=dati.sommario,
    )
    db.flush()

    ospite = _ospite_da_registrare(dati.ospite)
    if ospite is not None:
        OspiteRepository(db).add(
            host_id,
            Ospite(
                prenotazione_id=prenotazione.id,
                nome=ospite.nome,
                email=ospite.email,
                telefono=ospite.telefono,
                # `principale` è un'IDENTITÀ, non un ordine: l'Host ha indicato
                # QUESTO Ospite. Senza il flag `_principale` sceglierebbe
                # l'unico noto — comportamento identico oggi e diverso al primo
                # secondo Ospite, che è il modo in cui una scelta implicita
                # diventa un difetto molto dopo.
                principale=True,
            ),
        )
    db.commit()
    # Soli identificatori: un nome di Ospite scritto qui sopravviverebbe alla
    # retention che AD-21 gli impone (AD-16, NFR-11).
    logger.info(
        "prenotazione manuale creata",
        extra={
            "prenotazione_id": str(prenotazione.id),
            "host_id": str(host_id),
            "struttura_id": str(dati.struttura_id),
            "notti": soggiorno.nights,
            "con_ospite": ospite is not None,
        },
    )
    return prenotazione


def cancella_prenotazione(
    db: Session, host_id: uuid.UUID, prenotazione_id: uuid.UUID
) -> Prenotazione:
    """Porta una manuale a `cancellata` ed emette `prenotazione.cessata`.

    Solleva `PrenotazioneNonTrovataError` e `PrenotazioneNonManualeError`.

    **Non è una `DELETE`** (AD-19, AD-20): la riga resta, con la sua storia, e
    continua a comparire in griglia con la sua etichetta — farla sparire senza
    traccia contraddirebbe «archiviare, mai distruggere» agli occhi dell'Host,
    che quella prenotazione l'ha vista ieri. Che nessun percorso possa
    cancellarla è l'assenza che GS-6 impone su tutta la superficie.

    **Idempotente, e per costruzione.** La transizione è una `UPDATE`
    condizionata allo stato (`WHERE stato = 'attiva'`): l'evento si emette solo
    se quella `UPDATE` ha toccato una riga. Un doppio click non produce un
    secondo `prenotazione.cessata` — che nella 2.5 farebbe `decadere` due volte
    lo stesso Conflitto — né riscrive `cessata_il`, che è la decorrenza della
    retention (AD-21) e spostarla in avanti significherebbe conservare un dato
    personale più a lungo, un click alla volta.

    L'evento si scrive nella STESSA transazione della transizione (AD-1): non
    esiste uno stato `cancellata` senza il suo evento, né viceversa.
    """
    prenotazioni = PrenotazioneRepository(db)
    prenotazione = prenotazioni.by_id(host_id, prenotazione_id)
    if prenotazione is None:
        raise PrenotazioneNonTrovataError()
    if prenotazione.feed_id is not None:
        # Il sistema non scrive mai verso le OTA (AD-5, Non-Goal §8): una
        # Prenotazione da Feed «cancellata qui» divergerebbe dal portale, e il
        # primo sync riporterebbe indietro lo stato senza dire niente.
        raise PrenotazioneNonManualeError()
    struttura_id = prenotazione.struttura_id

    transizionate = prenotazioni.marca_cancellata(
        host_id, prenotazione_id=prenotazione_id, adesso=utcnow()
    )
    if transizionate == 0:
        # Era già cessata — dal click precedente, o da un'altra scheda. Nessun
        # evento, nessuna riscrittura: si risponde con lo stato corrente.
        db.commit()
        return prenotazione

    emit(
        db,
        EVENTO_PRENOTAZIONE_CESSATA,
        {
            "prenotazione_id": str(prenotazione_id),
            "host_id": str(host_id),
            "struttura_id": str(struttura_id),
        },
    )
    db.commit()
    logger.info(
        "prenotazione manuale cessata",
        extra={
            "prenotazione_id": str(prenotazione_id),
            "host_id": str(host_id),
            "struttura_id": str(struttura_id),
        },
    )
    return prenotazione


# ------------------------- azzeramento su richiesta (NFR-15, AD-21)


class OspiteNonTrovatoError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class EsitoAzzeramentoSuRichiesta:
    """Cosa è stato azzerato, in soli conteggi e identificatori (NFR-11)."""

    ambito: AmbitoAzzeramento
    riferimento: uuid.UUID
    anagrafiche_azzerate: int
    sommari_azzerati: int
    eseguito_il: datetime


def azzera_ospite_su_richiesta(
    db: Session, host_id: uuid.UUID, ospite_id: uuid.UUID, *, attore: str
) -> EsitoAzzeramentoSuRichiesta:
    """Cancellazione su richiesta di UN Ospite (NFR-15).

    L'Ospite si legge prima, e con l'`host_id` del perimetro: una richiesta su
    un Ospite che non è di quell'Host non è «zero righe azzerate», è una
    richiesta a cui non si può rispondere (AD-2). Distinguere le due cose è
    ciò che rende l'evidenza leggibile.
    """
    if OspiteRepository(db).by_id(host_id, ospite_id) is None:
        raise OspiteNonTrovatoError()
    return _azzera_su_richiesta(
        db,
        host_id,
        azzeramento.di_un_ospite(host_id, ospite_id),
        ambito=AmbitoAzzeramento.OSPITE,
        riferimento=ospite_id,
        attore=attore,
    )


def azzera_ospiti_dell_host_su_richiesta(
    db: Session, host_id: uuid.UUID, *, attore: str
) -> EsitoAzzeramentoSuRichiesta:
    """Cancellazione su richiesta di TUTTI gli Ospiti di un Host (NFR-15).

    L'Host si legge dal service di `identity`, mai dalla sua tabella (AD-18):
    un `host_id` inesistente deve produrre un errore, non un azzeramento
    riuscito su zero righe — cioè una richiesta dichiarata evasa e mai evasa.
    """
    identity_service.leggi_host(db, host_id)
    return _azzera_su_richiesta(
        db,
        host_id,
        azzeramento.di_un_host(host_id),
        ambito=AmbitoAzzeramento.HOST,
        riferimento=host_id,
        attore=attore,
    )


def _azzera_su_richiesta(
    db: Session,
    host_id: uuid.UUID,
    selezione: azzeramento.Selezione,
    *,
    ambito: AmbitoAzzeramento,
    riferimento: uuid.UUID,
    attore: str,
) -> EsitoAzzeramentoSuRichiesta:
    """La STESSA procedura del job periodico, con la selezione della richiesta.

    Non c'è un azzeratore per il job e uno per la richiesta: c'è
    `azzeramento.esegui`, e cambia solo cosa gli si dà da selezionare. È la
    forma in cui «la cancellazione su richiesta riusa la stessa procedura»
    (AD-21) resta vera anche quando la procedura cambierà — il `sommario` è
    già la prova che cambia.

    `esegui_su_richiesta` è quella procedura più un passo che il job non può
    avere: il SIGILLO. Il job ripassa e compensa, la richiesta si evade una
    volta sola — senza sigillo, un `sommario` vuoto al momento della richiesta
    lasciava `anonimizzato_il` a `NULL` e il portale poteva ripubblicare il
    nome di chi aveva chiesto la cancellazione.

    Nessun `try/except`: qui un fallimento NON è recuperabile e deve arrivare
    al chiamante. Il savepoint del job serve a non spegnere un ciclo
    periodico; una richiesta che fallisce in silenzio direbbe a chi l'ha fatta
    che è stata evasa. Un solo `commit`, con l'audit nella stessa transazione
    delle UPDATE: «azzeramento senza evidenza» non è raggiungibile.
    """
    adesso = utcnow()
    esito = azzeramento.esegui_su_richiesta(db, selezione, adesso=adesso)
    AzzeramentoAuditRepository(db).add(
        host_id,
        AzzeramentoAudit(
            attore=attore,
            ambito=ambito,
            riferimento=riferimento,
            anagrafiche_azzerate=esito.anagrafiche,
            sommari_azzerati=esito.sommari,
            eseguito_il=adesso,
        ),
    )
    db.commit()
    # Soli conteggi e identificatori: i dati appena azzerati non possono
    # sopravvivere nei log all'azzeramento stesso (AD-16, NFR-11).
    logger.info(
        "azzeramento su richiesta eseguito",
        extra={
            "ambito": ambito.value,
            "riferimento": str(riferimento),
            "host_id": str(host_id),
            "anagrafiche_azzerate": esito.anagrafiche,
            "sommari_azzerati": esito.sommari,
        },
    )
    return EsitoAzzeramentoSuRichiesta(
        ambito=ambito,
        riferimento=riferimento,
        anagrafiche_azzerate=esito.anagrafiche,
        sommari_azzerati=esito.sommari,
        eseguito_il=adesso,
    )


def _principale(ospiti: list[Ospite]) -> Ospite | None:
    """L'Ospite che la griglia mostra: quello indicato, o l'unico noto.

    Con più Ospiti e nessuno indicato non se ne elegge uno d'ufficio: il
    primo in ordine di inserimento non è «il principale», è il primo, e
    presentarlo come tale sarebbe un'identità dedotta — la stessa cosa che
    l'invariante vieta di fare col `sommario`. In quel caso la griglia dice
    che l'Ospite non è indicato e mostra quanti sono.
    """
    indicato = [ospite for ospite in ospiti if ospite.principale]
    if indicato:
        return indicato[0]
    return ospiti[0] if len(ospiti) == 1 else None


# --------------------------------------------- calendario unificato (FR-4)


@dataclass(frozen=True, slots=True)
class VoceCalendario:
    """Una Prenotazione con ciò che serve a mostrarla, già derivato."""

    prenotazione: Prenotazione
    ospite_principale: str | None
    altri_ospiti: int


@dataclass(frozen=True, slots=True)
class StrutturaDelCalendario:
    """Id e nome di una Struttura, copiati al confine fra i moduli.

    `calendario` non tipizza nulla sull'entità di un altro modulo: legge dal
    suo service e tiene ciò che gli serve. Portarsi dietro l'oggetto
    `Struttura` significherebbe che una colonna aggiunta in `strutture`
    arriva fino alla risposta del Calendario senza che nessuno l'abbia
    deciso (AD-1, AD-18).
    """

    id: uuid.UUID
    nome: str


@dataclass(frozen=True, slots=True)
class Calendario:
    da: date
    a: date
    stato: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    feed_collegati: int
    feed_mai_sincronizzati: int
    feed_in_errore: int
    strutture: list[StrutturaDelCalendario]
    voci: list[VoceCalendario]


# Precedenza fra gli stati di sync dei Feed aggregati: il peggiore vince.
# Un solo portale in errore rende la vista incompleta, e l'aggregato deve
# dirlo — non annegarlo nella media degli altri.
_PEGGIORE = (
    StatoSincronizzazione.FALLITO,
    StatoSincronizzazione.IN_CORSO,
    StatoSincronizzazione.MAI_SINCRONIZZATO,
    StatoSincronizzazione.RIUSCITO,
)


def calendario(
    db: Session,
    host_id: uuid.UUID,
    *,
    da: date,
    a: date,
    struttura_id: uuid.UUID | None = None,
) -> Calendario:
    """La griglia unificata di un periodo (FR-4, UX-DR1, NFR-2, AD-14).

    Un solo perimetro governa tutto: se `struttura_id` è dato, la Struttura
    si legge dal service di `strutture` — che solleva per una Struttura di
    un altro Host — e Prenotazioni e Feed si filtrano su di essa. La vista
    aggregata e la singola Struttura sono la stessa lettura con un filtro
    diverso, che è la ragione per cui il selettore non cambia schermata.

    Ogni valore che la griglia mostrerà è derivato QUI: notti, Ospite
    principale, conteggio degli altri, stato di sincronizzazione. Il
    frontend li presenta e non li ricalcola (AD-14) — il modo realistico in
    cui quell'invariante si perde è che il client rifaccia un conto «uguale»
    con la timezone del browser, e allora smettono di coincidere il giorno
    del cambio d'ora.
    """
    if struttura_id is not None:
        elencate = [strutture_service.leggi_struttura(db, host_id, struttura_id)]
    else:
        elencate = strutture_service.lista_strutture(db, host_id)
    strutture = [
        StrutturaDelCalendario(id=riga.id, nome=riga.nome) for riga in elencate
    ]

    prenotazioni = PrenotazioneRepository(db).nel_periodo(
        host_id, da=da, a=a, struttura_id=struttura_id
    )
    ospiti = OspiteRepository(db).per_prenotazioni(
        host_id, [riga.id for riga in prenotazioni]
    )
    voci = []
    for riga in prenotazioni:
        registrati = ospiti.get(riga.id, [])
        principale = _principale(registrati)
        voci.append(
            VoceCalendario(
                prenotazione=riga,
                ospite_principale=None if principale is None else principale.nome,
                altri_ospiti=len(registrati) - (0 if principale is None else 1),
            )
        )

    stato = _stato_aggregato(db, host_id, struttura_id=struttura_id)
    return Calendario(
        da=da,
        a=a,
        stato=stato.stato,
        ultimo_sync_riuscito_il=stato.ultimo_sync_riuscito_il,
        feed_collegati=stato.collegati,
        feed_mai_sincronizzati=stato.mai_sincronizzati,
        feed_in_errore=stato.in_errore,
        strutture=strutture,
        voci=voci,
    )


@dataclass(frozen=True, slots=True)
class StatoAggregato:
    stato: StatoSincronizzazione
    ultimo_sync_riuscito_il: datetime | None
    collegati: int
    mai_sincronizzati: int
    in_errore: int


def _stato_aggregato(
    db: Session, host_id: uuid.UUID, *, struttura_id: uuid.UUID | None
) -> StatoAggregato:
    """La verità temporale di una vista che aggrega più Feed (NFR-2, UX-DR6).

    Il timestamp è il **minimo** fra gli ultimi sync riusciti, e diventa
    `None` appena un Feed non ne ha mai avuto uno: la vista non è più
    fresca del suo Feed più vecchio, e con un Feed muto non esiste un
    orario che descriva l'insieme.
    """
    feed = FeedIcalRepository(db).dell_host(host_id, struttura_id=struttura_id)
    if not feed:
        return StatoAggregato(
            stato=StatoSincronizzazione.MAI_SINCRONIZZATO,
            ultimo_sync_riuscito_il=None,
            collegati=0,
            mai_sincronizzati=0,
            in_errore=0,
        )

    stati = [stato_del_feed(db, host_id, riga) for riga in feed]
    orari = [riga.ultimo_sync_riuscito_il for riga in stati]
    return StatoAggregato(
        stato=min(
            (riga.stato for riga in stati),
            key=_PEGGIORE.index,
        ),
        ultimo_sync_riuscito_il=None if None in orari else min(orari),  # type: ignore[type-var]
        collegati=len(feed),
        mai_sincronizzati=sum(1 for orario in orari if orario is None),
        in_errore=sum(
            1 for riga in stati if riga.stato is StatoSincronizzazione.FALLITO
        ),
    )


def _categoria(errore: ErroreDiTrasporto) -> CategoriaErroreSync:
    if isinstance(errore, TimeoutFeedError):
        return CategoriaErroreSync.TIMEOUT
    if isinstance(errore, RispostaTroppoGrandeError):
        return CategoriaErroreSync.RISPOSTA_TROPPO_GRANDE
    if isinstance(errore, EsitoHttpInattesoError):
        return CategoriaErroreSync.ESITO_HTTP_INATTESO
    return CategoriaErroreSync.URL_NON_RAGGIUNGIBILE


def _scrivi_run(
    db: Session,
    feed: FeedIcal,
    *,
    iniziato_il: datetime,
    esito: EsitoSyncRun,
    categoria: CategoriaErroreSync | None = None,
    conteggi: EsitoImport | None = None,
    non_modificato: bool = False,
) -> SyncRun:
    contatori = conteggi or EsitoImport()
    run = SyncRunRepository(db).add(
        feed.host_id,
        SyncRun(
            feed_id=feed.id,
            esito=esito,
            categoria_errore=categoria,
            prenotazioni_importate=contatori.importate,
            prenotazioni_aggiornate=contatori.aggiornate,
            prenotazioni_rimosse_dal_feed=contatori.rimosse_dal_feed,
            prenotazioni_ricomparse=contatori.ricomparse,
            eventi_malformati=contatori.malformati,
            eventi_ricorrenti_non_espansi=contatori.ricorrenti_non_espansi,
            non_modificato=non_modificato,
            iniziato_il=iniziato_il,
            concluso_il=utcnow(),
        ),
    )
    # `flush` prima di contare: il run appena scritto DEVE essere fra quelli
    # che l'alert conta, altrimenti la soglia scatterebbe con un giro di
    # ritardo — cioè al fallimento N+1, non all'N.
    db.flush()
    if esito is EsitoSyncRun.FALLITO:
        _valuta_alert_fallimenti(db, feed, categoria)
    return run


def _valuta_alert_fallimenti(
    db: Session, feed: FeedIcal, categoria: CategoriaErroreSync | None
) -> None:
    """Alert interno all'ATTRAVERSAMENTO della soglia (AR-10, NFR-1).

    Solo all'attraversamento, non a ogni fallimento oltre la soglia: un
    portale giù per un giorno produrrebbe novantasei righe identiche, e un
    alert che si ripete è un alert che si impara a ignorare. Il fatto nuovo è
    «questo Feed ha smesso di funzionare», e succede una volta sola per
    guasto — al successivo successo il contatore torna a zero da sé
    (`fallimenti_consecutivi` è derivato) e un nuovo guasto tornerà a
    segnalare.

    L'artefatto è un log strutturato: NFR-7 mappa metriche e canali di alert
    sull'Epic 3, quindi qui non esiste ancora un canale verso cui uscire. Il
    log è il minimo verificabile proposto dal test design (§4.2-9) e non
    pregiudica quella scelta — è un `logger.error` con i campi già pronti per
    essere raccolti.
    """
    soglia = get_settings().feed_sync_fallimenti_per_alert
    consecutivi = SyncRunRepository(db).fallimenti_consecutivi(feed.host_id, feed.id)
    if consecutivi != soglia:
        return
    logger.error(
        "alert: feed non sincronizza da %s tentativi consecutivi",
        consecutivi,
        extra={
            "feed_id": str(feed.id),
            "host_id": str(feed.host_id),
            "struttura_id": str(feed.struttura_id),
            "fallimenti_consecutivi": consecutivi,
            "soglia": soglia,
            "categoria_errore": None if categoria is None else categoria.value,
        },
    )


def esegui_sync(
    db: Session,
    host_id: uuid.UUID,
    feed_id: uuid.UUID,
    *,
    client: ClientFeed | None = None,
) -> SyncRun:
    """Un run di sincronizzazione. Scrive SEMPRE un `sync_run`.

    Non solleva sugli errori di feed o di rete: li registra. Un run fallito
    che non lascia traccia renderebbe «non sincronizzo da tre giorni»
    indistinguibile da «non ci sono novità» (NFR-2), e il SAVEPOINT per item
    del worker (G-1) annullerebbe la scrittura insieme all'eccezione.
    """
    trasporto = client if client is not None else client_di_produzione()
    feed = leggi_feed(db, host_id, feed_id)
    iniziato_il = utcnow()

    try:
        # Richiesta CONDIZIONALE: se il portale non ha novità risponde 304 e
        # non ritrasmette il calendario (AD-4). I validatori vengono da
        # `feed`, cioè dall'ultimo import davvero riconciliato — mai da un run
        # fallito, altrimenti chiederemmo «è cambiato rispetto a una cosa che
        # non abbiamo?» e ci sentiremmo rispondere «no».
        risposta = trasporto.scarica(
            feed.url, validatori=Validatori(feed.etag, feed.last_modified)
        )
    except ErroreDiTrasporto as exc:
        logger.warning(
            "sync del feed fallito nel trasporto",
            extra={"feed_id": str(feed.id), "url": url_redatto(feed.url)},
        )
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=_categoria(exc),
        )

    if risposta.non_modificato:
        # Il portale conferma che i validatori che gli abbiamo mandato sono
        # ancora buoni: non c'è corpo, quindi non c'è NULLA da riconciliare.
        #
        # È l'interazione che il test design marca come il rischio peggiore
        # dell'Epic (R2-C): un 304 letto come «il feed è arrivato ed è vuoto»
        # marcherebbe `rimossa_dal_feed` l'intero calendario, con esito
        # riuscito e quindi in silenzio. Il ritorno anticipato qui è la
        # ragione per cui non può succedere — non c'è nessun percorso da
        # questa riga a `_riconcilia`.
        #
        # Il run è comunque RIUSCITO e il suo timestamp fa avanzare «dati
        # aggiornati alle HH:MM»: abbiamo davvero verificato con il portale
        # che i dati che mostriamo sono correnti, ed è esattamente ciò che
        # NFR-2 chiede di dire all'Host.
        _memorizza_validatori(db, feed, risposta)
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.RIUSCITO,
            non_modificato=True,
        )

    try:
        analizzato = ical.analizza_feed(risposta.corpo)
    except ical.FeedNonValidoError:
        # E2-G3: il corpo non è un calendario completo. NESSUNA transizione.
        logger.warning(
            "sync del feed fallito: corpo non valido", extra={"feed_id": str(feed.id)}
        )
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=CategoriaErroreSync.FEED_NON_VALIDO,
        )

    # TUTTI gli uid letti dal feed, compresi quelli di eventi che non si
    # normalizzano: un evento malformato è comunque presente nel feed, e
    # trattarlo come scomparso marcherebbe `rimossa_dal_feed` una
    # Prenotazione viva.
    uid_presenti = [
        vevent.uid for vevent in analizzato.eventi if vevent.uid is not None
    ]
    if not uid_presenti:
        # Due casi, una sola conclusione. Un calendario chiuso ma senza eventi
        # e un calendario i cui eventi non portano un `UID` utilizzabile sono
        # entrambi indistinguibili da un export andato male, e in entrambi
        # l'insieme degli uid presenti è vuoto — cioè l'insieme rispetto al
        # quale si decide chi è «scomparso».
        #
        # Il costo dei due errori non è simmetrico: trattarli come «tutto
        # scomparso» svuoterebbe il calendario e farebbe `decadere` i
        # Conflitti aperti, con esito RIUSCITO e quindi in silenzio; trattarli
        # come run fallito costa un errore visibile su un Feed che davvero non
        # ha prenotazioni identificabili. Si sceglie il secondo.
        return _scrivi_run(
            db,
            feed,
            iniziato_il=iniziato_il,
            esito=EsitoSyncRun.FALLITO,
            categoria=CategoriaErroreSync.FEED_SENZA_EVENTI,
        )

    conteggi = _riconcilia(db, feed, analizzato, uid_presenti)
    # DOPO la riconciliazione, mai prima: il validatore certifica che questo
    # corpo è entrato nel database. Scriverlo prima significherebbe che un
    # errore a metà riconciliazione lascerebbe un validatore che promette
    # dati che non abbiamo, e il prossimo 304 congelerebbe il Feed su di essi.
    _memorizza_validatori(db, feed, risposta)
    return _scrivi_run(
        db,
        feed,
        iniziato_il=iniziato_il,
        esito=EsitoSyncRun.RIUSCITO,
        conteggi=conteggi,
    )


def _memorizza_validatori(db: Session, feed: FeedIcal, risposta: RispostaFeed) -> None:
    FeedIcalRepository(db).aggiorna_validatori(
        feed.host_id,
        feed_id=feed.id,
        etag=risposta.etag,
        last_modified=risposta.last_modified,
    )


def _riconcilia(
    db: Session,
    feed: FeedIcal,
    analizzato: ical.FeedAnalizzato,
    uid_presenti: list[str],
) -> EsitoImport:
    """Upsert degli eventi e transizione degli scomparsi. Mai una DELETE."""
    prenotazioni = PrenotazioneRepository(db)
    importate = aggiornate = ricomparse = malformati = ricorrenti = 0

    for vevent in analizzato.eventi:
        try:
            evento = normalizza(vevent)
        except Exception as exc:
            # `normalizza` è PURA: nessun I/O, nessuna sessione. Qui si può
            # catturare largo senza rischiare di proseguire su una transazione
            # abortita, e va fatto: il contenuto è di terze parti, quindi
            # l'insieme dei modi in cui può essere illeggibile non è
            # enumerabile a priori. Un'eccezione che sfugge risalirebbe fino
            # al SAVEPOINT per item del worker, annullando la riga `sync_run`
            # insieme all'errore — e il Feed tornerebbe a
            # «mai sincronizzato» senza categoria d'errore, cioè il
            # fallimento silenzioso che AC 7 e AC 5 vietano.
            #
            # L'uid resta in `uid_presenti` (calcolato a monte): un evento
            # illeggibile è comunque NEL feed, non scomparso.
            malformati += 1
            logger.info(
                "VEVENT non normalizzabile: registrato come malformato",
                extra={"feed_id": str(feed.id), "motivo": type(exc).__name__},
            )
            continue
        if evento.ricorrente:
            ricorrenti += 1
        esito = _upsert(prenotazioni, feed, evento)
        if esito == "importata":
            importate += 1
        elif esito == "ricomparsa":
            ricomparse += 1
        else:
            aggiornate += 1

    rimosse = prenotazioni.marca_rimosse_dal_feed(
        feed.host_id, feed_id=feed.id, uid_presenti=uid_presenti
    )
    logger.info(
        "sync del feed concluso",
        extra={
            "feed_id": str(feed.id),
            "importate": importate,
            "aggiornate": aggiornate,
            "rimosse_dal_feed": rimosse,
        },
    )
    return EsitoImport(
        importate=importate,
        aggiornate=aggiornate,
        rimosse_dal_feed=rimosse,
        ricomparse=ricomparse,
        malformati=malformati,
        ricorrenti_non_espansi=ricorrenti,
    )


def _upsert(
    prenotazioni: PrenotazioneRepository, feed: FeedIcal, evento: EventoFeed
) -> str:
    return prenotazioni.upsert_dal_feed(
        feed.host_id,
        feed_id=feed.id,
        struttura_id=feed.struttura_id,
        canale=feed.canale,
        ical_uid=evento.ical_uid,
        check_in=evento.soggiorno.check_in,
        check_out=evento.soggiorno.check_out,
        sommario=evento.sommario,
        cancellata=evento.cancellato,
    )


__all__ = [
    "EVENTO_PRENOTAZIONE_CESSATA",
    "Calendario",
    "DatiFeed",
    "DatiOspite",
    "DatiPrenotazioneManuale",
    "EsitoAzzeramentoSuRichiesta",
    "EsitoImport",
    "FeedNonTrovatoError",
    "OspiteNonTrovatoError",
    "PrenotazioneNonManualeError",
    "PrenotazioneNonTrovataError",
    "StatoFeed",
    "StrutturaDelCalendario",
    "UrlFeedNonValidoError",
    "VoceCalendario",
    "azzera_ospite_su_richiesta",
    "azzera_ospiti_dell_host_su_richiesta",
    "calendario",
    "cancella_prenotazione",
    "client_di_produzione",
    "collega_feed",
    "crea_prenotazione_manuale",
    "esegui_sync",
    "leggi_feed",
    "lista_feed",
    "ospiti_della_prenotazione",
    "prenotazioni_del_feed",
    "registra_ospite",
    "stato_del_feed",
    "ultimo_run",
    "ultimo_run_riuscito",
]
