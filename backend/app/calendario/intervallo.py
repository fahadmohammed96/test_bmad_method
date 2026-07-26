"""Ogni quanto risincronizzare un Feed (G3-5, AD-10) — funzione PURA.

Nessuna sessione, nessun orologio interno, nessuna configurazione letta da
qui: `adesso`, il prossimo check-in e i parametri entrano come argomenti.
È la condizione perché l'intervallo si possa provare in millisecondi invece
che aspettando quindici minuti (test design §5.4, «determinismo temporale»).

**Su cosa questa funzione NON decide.** `epics.md` dice «adattivo fino a 5
minuti in prossimità di check-in» e non quantifica «in prossimità»: quante
ore prima, e rispetto al check-in di quale Prenotazione. Il test design lo
registra come voce §4.2-8 aperta e propone «tre parametri di configurazione e
un AC riscritto in termini di parametri». Questa funzione implementa quella
proposta — finestra, intervallo pieno e intervallo minimo sono tutti e tre
parametri — e non sceglie una soglia al posto di chi deve deciderla. Finché
§4.2-8 è aperta, l'AC 10 resta tracciato come non chiudibile.

La forma della regola, invece, è una scelta di ingegneria e la si dichiara:
la funzione è a **gradino**, non a rampa. Una rampa continua produrrebbe un
`due_at` diverso a ogni giro e renderebbe il comportamento del poller
difficile da leggere in un `job` — mentre il valore che l'intervallo protegge
(vedere presto una cancellazione last-minute) è tutto dentro la finestra, non
distribuito su di essa.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.core.date_range import TZ_ROME


class ParametriIntervalloNonValidiError(ValueError):
    """Configurazione che renderebbe il poller inerte o impazzito."""


@dataclass(frozen=True, slots=True)
class ParametriIntervallo:
    """I tre parametri di §4.2-8, validati alla costruzione.

    Validati e non solo documentati: un `feed_sync_intervallo_minuti = 0`
    letto dall'ambiente farebbe riprogrammare il job su `due_at = adesso`, e
    il poller girerebbe in ciclo stretto consumando la coda di tutti gli Host.
    Un parametro di configurazione sbagliato deve fermare l'avvio, non
    degradare in un difetto di regime che nessuno collega alla causa.
    """

    intervallo_minuti: int
    intervallo_minimo_minuti: int
    finestra_prossimita_ore: int

    def __post_init__(self) -> None:
        if self.intervallo_minimo_minuti < 1:
            raise ParametriIntervalloNonValidiError(
                "l'intervallo minimo di sync deve essere almeno 1 minuto"
            )
        if self.intervallo_minuti < self.intervallo_minimo_minuti:
            raise ParametriIntervalloNonValidiError(
                "l'intervallo pieno di sync non può essere più corto del minimo"
            )
        if self.finestra_prossimita_ore < 0:
            raise ParametriIntervalloNonValidiError(
                "la finestra di prossimità non può essere negativa"
            )


def intervallo_di_sync(
    *,
    adesso: datetime,
    prossimo_check_in: date | None,
    parametri: ParametriIntervallo,
) -> timedelta:
    """Quanto attendere prima del prossimo sync di questo Feed.

    `prossimo_check_in` è una data di calendario Europe/Rome (AD-3); il
    confronto avviene sull'ISTANTE d'inizio di quel giorno nel fuso locale,
    non su una sottrazione fra date. Sottrarre date perderebbe l'ora, e in
    prossimità di un cambio d'ora perderebbe anche i sessanta minuti che
    l'intera regola esiste per proteggere.

    Un check-in già iniziato (o in corso) non accorcia niente: la finestra è
    quella che PRECEDE l'arrivo, ed è lì che una cancellazione tardiva non
    vista si trasforma in un ospite davanti a una porta chiusa.
    """
    pieno = timedelta(minutes=parametri.intervallo_minuti)
    if prossimo_check_in is None:
        return pieno

    arrivo = datetime.combine(
        prossimo_check_in, datetime.min.time(), tzinfo=TZ_ROME
    ).astimezone(adesso.tzinfo)
    mancante = arrivo - adesso
    if mancante <= timedelta(0):
        return pieno
    if mancante > timedelta(hours=parametri.finestra_prossimita_ore):
        return pieno
    return timedelta(minutes=parametri.intervallo_minimo_minuti)
