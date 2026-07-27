"""Retention dell'anagrafica Ospite (AD-21) — la regola, PURA.

AD-21 è l'unica fonte di periodo e decorrenza, e dice due cose:

- il **periodo** è un parametro di configurazione legato al ciclo della
  Prenotazione, mai una costante nel codice (valore iniziale provvisorio in
  attesa di R-5);
- la **decorrenza** è il `check_out`, **o l'uscita dallo stato `attiva`
  (AD-19) se precedente**.

Qui vive solo la regola: nessuna sessione, nessun orologio interno, nessuna
configurazione letta da dentro. `adesso` e il periodo entrano come argomenti,
così il confine si prova in millisecondi invece che aspettando novanta giorni
— la stessa disciplina di `intervallo.py`.

**Perché un LIMITE e non una scadenza per riga.** La domanda «questa
anagrafica è scaduta?» si può porre in due modi: calcolando la scadenza di
ogni riga e confrontandola con adesso, oppure calcolando **una volta** il
confine e confrontandolo con i dati della riga. Il secondo modo è l'unico che
un `WHERE` sa fare senza convertire timezone dentro il database, ed è la
ragione per cui la regola e la query non sono due implementazioni della stessa
cosa: la query filtra sui **due campi** di `LimiteRetention`, che è
esattamente ciò che `scaduta` confronta.

**L'equivalenza su cui poggia tutto.** La decorrenza dal `check_out` è
l'istante d'inizio di quel giorno in Europe/Rome (AD-3: le date di
Prenotazione sono date locali, non istanti). Vale:

    mezzanotte_rome(d) <= t   ⟺   d <= rome_day(t)

— in un verso perché `mezzanotte_rome(rome_day(t)) <= t` sempre, nell'altro
perché da `d > rome_day(t)` segue che `mezzanotte_rome(d)` non è prima della
mezzanotte del giorno dopo `rome_day(t)`, che è già oltre `t`. Regge
attraverso i cambi d'ora legale, dove una sottrazione fra date perderebbe i
sessanta minuti che separano lo scaduto dal non scaduto.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import ColumnElement, and_, or_

from app.calendario.models import Prenotazione
from app.core.date_range import rome_day


class PeriodoRetentionNonValidoError(ValueError):
    """Un periodo nullo o negativo azzererebbe l'anagrafica appena scritta."""


@dataclass(frozen=True, slots=True)
class LimiteRetention:
    """Il confine, calcolato una volta sola per esecuzione del job.

    `istante` serve a confrontare `cessata_il`, che è un timestamp;
    `giorno` serve a confrontare `check_out`, che è una data locale. Sono le
    due metà della stessa domanda, e vivono insieme perché derivano dallo
    stesso `adesso`: calcolarle in due punti diversi significherebbe leggere
    l'orologio due volte e poter cadere ai lati opposti di un confine.
    """

    istante: datetime
    giorno: date


def limite_retention(*, adesso: datetime, periodo: timedelta) -> LimiteRetention:
    """Confine oltre il quale l'anagrafica è scaduta. Solleva se il periodo è ≤ 0.

    Validato e non solo documentato: un `ospite_retention_giorni = 0` letto
    dall'ambiente farebbe azzerare i contatti della Prenotazione in corso, e
    il dato azzerato non torna. Un parametro di configurazione sbagliato deve
    fermare l'avvio, non distruggere dati in silenzio.
    """
    if periodo <= timedelta(0):
        raise PeriodoRetentionNonValidoError(
            "il periodo di retention dell'anagrafica Ospite deve essere positivo"
        )
    istante = adesso - periodo
    return LimiteRetention(istante=istante, giorno=rome_day(istante))


def scaduta(
    *, check_out: date, cessata_il: datetime | None, limite: LimiteRetention
) -> bool:
    """L'anagrafica legata a questa Prenotazione ha superato la retention?

    Due decorrenze, e vince la più vicina nel tempo: il `check_out`, oppure
    l'uscita da `attiva` **se precedente**. Una Prenotazione cancellata sei
    mesi prima dell'arrivo non tiene i contatti per sei mesi più il periodo:
    quel soggiorno non avverrà, e la ragione per cui i contatti erano lì è
    finita nell'istante della cancellazione.

    Il caso opposto — uscita da `attiva` DOPO il `check_out`, cioè una
    Prenotazione conclusa e poi archiviata — non sposta niente in avanti: il
    `check_out` ha già fatto decorrere il periodo.
    """
    if check_out <= limite.giorno:
        return True
    return cessata_il is not None and cessata_il <= limite.istante


def filtro_scadute(limite: LimiteRetention) -> ColumnElement[bool]:
    """La stessa regola di `scaduta`, come predicato SQL su `prenotazione`.

    Due espressioni della stessa regola sono un rischio di divergenza, e la
    scelta è di tenerle a poche righe di distanza invece che in due file:
    `tests/test_retention_ospite.py::test_la_regola_e_il_filtro_concordano`
    le confronta su una tabella di casi al confine — cambiare una senza
    l'altra diventa rosso, non un difetto che si scopre novanta giorni dopo
    su dati che non tornano.

    Il job non può fare altrimenti: selezionare tutte le anagrafiche e
    filtrarle in Python significherebbe leggere l'intera tabella a ogni
    giro. Ed è la ragione per cui `LimiteRetention` porta con sé già
    convertiti i due valori che il `WHERE` confronta — così la conversione
    di fuso orario resta in Python, dove è testata, invece di finire dentro
    una funzione del database.
    """
    return or_(
        Prenotazione.check_out <= limite.giorno,
        and_(
            Prenotazione.cessata_il.is_not(None),
            Prenotazione.cessata_il <= limite.istante,
        ),
    )
