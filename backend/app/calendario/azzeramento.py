"""La procedura di azzeramento dei campi personali (AD-21) — UNA sola.

AD-21 dice che la cancellazione su richiesta GDPR (NFR-15) «riusa la stessa
procedura di azzeramento» del job periodico. Perché quella frase sia vera e
resti vera, la procedura vive qui e la **selezione** è un parametro: il job
passa il filtro di scadenza, l'endpoint interno passa un Ospite o un Host.
Scrivere un secondo azzeratore darebbe due implementazioni che divergono al
primo cambiamento — e la prima cosa che divergerebbe è proprio il campo
aggiunto per ultimo, cioè il `sommario`.

**Due UPDATE, non una.** L'anagrafica sta su `ospite`, il `sommario` sta su
`prenotazione`, e la seconda NON è un'estensione della prima: l'Ospite non
nasce mai dal sync — l'unico percorso di scrittura è quello manuale dell'Host
— quindi il caso primario è la Prenotazione scaduta con il nome dentro il
`SUMMARY` e **nessuna riga `ospite`**. Azzerare il `sommario` come colonna in
più della `UPDATE` su `ospite` lo mancherebbe al 100%.

**Il filtro chiede «c'è qualcosa da azzerare?», mai «l'ho già fatto?».**
Entrambe le UPDATE si selezionano sui CAMPI (contatti non nulli, `sommario`
non nullo) e non su `anonimizzato_il IS NULL`: un dato reinserito dopo un
azzeramento non scadrebbe mai più. La guardia di non-ripopolamento da un sync
è un'altra cosa e vive nell'upsert (`repository.py`), che è l'unico punto in
cui un `sommario` può tornare senza che nessuno l'abbia scritto a mano.

Qui non si cattura nulla e non si fa `commit`: chi chiama decide se un
fallimento è recuperabile (il job lo è, e si protegge con un savepoint
interno) e quando chiudere la transazione.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import ColumnElement, Update, and_, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.calendario.models import Ospite, Prenotazione


@dataclass(frozen=True, slots=True)
class Selezione:
    """Su quali righe agire, espressa una volta per ciascuna delle due tabelle.

    Due predicati e non uno, perché le due domande non coincidono: «gli
    Ospiti di questa richiesta» e «le Prenotazioni il cui `sommario` va
    azzerato» si sovrappongono nel caso della retention e divergono nel caso
    del singolo Ospite. Costruirle insieme, nei costruttori qui sotto, è ciò
    che impedisce a un chiamante di passarne una sola.
    """

    ospiti: ColumnElement[bool]
    prenotazioni: ColumnElement[bool]


@dataclass(frozen=True, slots=True)
class EsitoAzzeramento:
    """Quante righe sono state toccate, per tabella. Nessun dato personale."""

    anagrafiche: int
    sommari: int


def per_prenotazioni(predicato: ColumnElement[bool]) -> Selezione:
    """Selezione guidata dalle Prenotazioni: è la forma del job di retention.

    Il predicato è quello di `retention.filtro_scadute`, e vale su **entrambi**
    i lati: gli Ospiti sono quelli legati a una Prenotazione selezionata, il
    `sommario` è quello delle Prenotazioni selezionate — indipendentemente dal
    fatto che un Ospite esista. È la metà che si perde partendo dall'Ospite.
    """
    return Selezione(
        ospiti=Ospite.prenotazione_id.in_(select(Prenotazione.id).where(predicato)),
        prenotazioni=predicato,
    )


def di_un_ospite(host_id: uuid.UUID, ospite_id: uuid.UUID) -> Selezione:
    """Un solo Ospite, e il `sommario` della sua Prenotazione (NFR-15).

    Il `sommario` entra anche qui, e la ragione è la stessa che AD-21 dà per
    la retention: il `SUMMARY` dei feed OTA contiene spesso il nome
    dell'Ospite, quindi azzerare la sua anagrafica lasciandolo in vita
    vanificherebbe la richiesta. Se sulla stessa Prenotazione sono registrati
    altri Ospiti, le loro anagrafiche NON si toccano — il `sommario` è testo
    opaco del portale, non l'anagrafica di nessuno, e resta un campo azzerato
    su una riga che sopravvive intatta (AD-20).

    `host_id` su entrambi i lati: la tenancy non si eredita dalla riga che si
    è appena letta, si scrive nel predicato (AD-2).
    """
    prenotazione_dell_ospite = select(Ospite.prenotazione_id).where(
        Ospite.host_id == host_id, Ospite.id == ospite_id
    )
    return Selezione(
        ospiti=and_(Ospite.host_id == host_id, Ospite.id == ospite_id),
        prenotazioni=and_(
            Prenotazione.host_id == host_id,
            Prenotazione.id.in_(prenotazione_dell_ospite),
        ),
    )


def di_un_host(host_id: uuid.UUID) -> Selezione:
    """Tutti gli Ospiti di un Host, e i `sommario` delle sue Prenotazioni."""
    return Selezione(
        ospiti=Ospite.host_id == host_id,
        prenotazioni=Prenotazione.host_id == host_id,
    )


def esegui(db: Session, selezione: Selezione, *, adesso: datetime) -> EsitoAzzeramento:
    """Azzera i campi personali della selezione. MAI una DELETE (AD-20, GS-6).

    È la procedura del job periodico: tocca solo ciò che ha davvero qualcosa
    da azzerare. Il percorso su richiesta parte da qui e aggiunge un passo —
    vedi `esegui_su_richiesta`, e la ragione per cui non può essere lo stesso.
    """
    return EsitoAzzeramento(
        anagrafiche=_azzera_anagrafiche(db, selezione, adesso),
        sommari=_azzera_sommari(db, selezione, adesso),
    )


def esegui_su_richiesta(
    db: Session, selezione: Selezione, *, adesso: datetime
) -> EsitoAzzeramento:
    """La stessa procedura, più il SIGILLO: la richiesta si evade una volta.

    Il job e la richiesta hanno bisogni **opposti** sullo stesso predicato, e
    il punto in cui si incontrano è dove il difetto nasceva.

    Il job chiede «c'è qualcosa da azzerare?» e può permetterselo perché
    **ripassa**: se il `sommario` rientra da un sync, il giro dopo lo ritoglie.
    Filtrare diversamente reintrodurrebbe la trappola 2 — un dato reinserito
    che non scade mai più. Quel filtro non si tocca.

    La richiesta NFR-15 si evade **una volta sola**, e non ha compensazione:
    se al momento della richiesta il `sommario` era vuoto, nessuna riga veniva
    toccata, `anonimizzato_il` restava `NULL`, la guardia dell'upsert non si
    armava — e il portale poteva ripubblicare dopo un `SUMMARY` col nome di
    chi aveva chiesto la cancellazione. Su un soggiorno futuro il job di
    retention non passerà per anni. La durabilità di un adempimento non può
    dipendere da come stava per caso quel campo in quell'istante.

    Da qui il sigillo, che è un passo dichiarato e non un filtro diverso:
    dopo una richiesta, ogni Prenotazione selezionata porta `anonimizzato_il`,
    quindi l'upsert non le scriverà più un `sommario`.

    **Cosa attesta `anonimizzato_il` dopo questo passo.** Sul percorso del job
    significa «questo campo è stato azzerato». Qui significa, più
    precisamente, «su questa riga la richiesta NFR-15 è stata evasa» — che è
    avvenuto davvero, anche quando non c'era nulla da cancellare. La
    distinzione non si perde: `EsitoAzzeramento.sommari` conta le righe
    davvero azzerate ed è ciò che finisce nell'audit, quindi «evaso senza
    trovare nulla» resta leggibile come `sommari_azzerati = 0`.

    Il sigillo vale **solo** per il `sommario`. Sul lato `ospite` AD-21 non
    vieta il ripopolamento — dalla Story 2.4 l'Host può reinserire un
    contatto, e quel dato tornerà a scadere col job. L'asimmetria è
    dell'invariante, non una svista.
    """
    esito = esegui(db, selezione, adesso=adesso)
    _sigilla_sommari(db, selezione, adesso)
    return esito


def _azzera_anagrafiche(db: Session, selezione: Selezione, adesso: datetime) -> int:
    return _righe(
        db,
        update(Ospite)
        .where(
            or_(
                Ospite.nome.is_not(None),
                Ospite.email.is_not(None),
                Ospite.telefono.is_not(None),
            ),
            selezione.ospiti,
        )
        .values(
            nome=None,
            email=None,
            telefono=None,
            anonimizzato_il=adesso,
            aggiornato_il=adesso,
        ),
    )


def _azzera_sommari(db: Session, selezione: Selezione, adesso: datetime) -> int:
    """Il `sommario`, con il PROPRIO predicato di «c'è qualcosa da azzerare?».

    `sommario IS NOT NULL` e non l'esistenza di un Ospite: è il caso primario
    — il nome sta solo nel `SUMMARY` e nessuna riga `ospite` esiste. Ed è
    anche ciò che rende l'operazione idempotente per costruzione: al secondo
    giro non c'è nulla da azzerare, quindi né `anonimizzato_il` né
    `aggiornata_il` si muovono.
    """
    return _righe(
        db,
        update(Prenotazione)
        .where(Prenotazione.sommario.is_not(None), selezione.prenotazioni)
        .values(sommario=None, anonimizzato_il=adesso, aggiornata_il=adesso),
    )


def _sigilla_sommari(db: Session, selezione: Selezione, adesso: datetime) -> int:
    """Marca `anonimizzato_il` sulle righe selezionate che ancora non l'hanno.

    Gira DOPO `_azzera_sommari`, quindi le righe davvero azzerate hanno già
    l'evidenza e questa istruzione non le tocca: `anonimizzato_il IS NULL`
    lascia fuori anche i sigilli di richieste precedenti, che è ciò che rende
    l'operazione idempotente — la prova di QUANDO la cancellazione è stata
    evasa è la prima, e una richiesta ripetuta non deve spostarla.

    È l'unico punto del codice in cui `anonimizzato_il IS NULL` compare in una
    selezione, e non è la trappola 2: quella riguarda il filtro del JOB, che
    chiede «c'è qualcosa da azzerare?» e resta sui campi.
    """
    return _righe(
        db,
        update(Prenotazione)
        .where(Prenotazione.anonimizzato_il.is_(None), selezione.prenotazioni)
        .values(anonimizzato_il=adesso, aggiornata_il=adesso),
    )


def _righe(db: Session, istruzione: Update) -> int:
    # `cast`: `Session.execute` è tipizzato genericamente, ma una UPDATE
    # restituisce sempre un CursorResult, che espone `rowcount`.
    return int(cast(CursorResult, db.execute(istruzione)).rowcount or 0)
