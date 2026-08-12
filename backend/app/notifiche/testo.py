"""Formati italiani per i testi delle notifiche (NFR-9, UX-DR11).

Il copy è **funzione pura del dato**: nessun orologio, nessuna sessione,
nessuna lettura. È la ragione per cui AC 9 sta a livello unit e non altrove.

Il frontend ha già il suo punto unico di formattazione (`lib/formati.ts`), che
usa `Intl` con locale `it-IT`. Qui non lo si può riusare — la notifica la
compone il worker, dove un browser non c'è — e non lo si vuole nemmeno
imitare: `Intl` in Python (`locale`) è un'impostazione **di processo**, cioè
uno stato globale che un altro thread può cambiare, e in CI il locale italiano
non è nemmeno installato. Il testo verrebbe in inglese senza che nulla
fallisca. Dodici nomi di mese sono un dato del dominio linguistico, non una
duplicazione della libreria standard.

**L'intervallo si stampa in notti, non in estremi.** Il soggiorno è
semiaperto [check_in, check_out) (AD-3): l'ultimo giorno dell'intervallo NON è
una notte, e scriverlo darebbe all'Host un giorno in più di quelli
effettivamente occupati — proprio nel messaggio con cui deve decidere se ha
una doppia prenotazione.
"""

from datetime import date, timedelta

MESI_IT = (
    "gennaio",
    "febbraio",
    "marzo",
    "aprile",
    "maggio",
    "giugno",
    "luglio",
    "agosto",
    "settembre",
    "ottobre",
    "novembre",
    "dicembre",
)


def _mese(giorno: date) -> str:
    return MESI_IT[giorno.month - 1]


def intervallo_it(check_in: date, check_out: date) -> str:
    """Le notti di [check_in, check_out) in italiano: «15-17 agosto».

    Regole, tutte derivate dal dato e da nient'altro:

    - una notte sola → «15 agosto»;
    - stesso mese → «15-17 agosto»;
    - mesi diversi → «30 agosto - 1 settembre»;
    - anni diversi → l'anno compare su entrambi gli estremi, perché
      «30 dicembre - 1 gennaio» non dice quale dei due anni sia quale.

    L'anno NON dipende da quale sia l'anno corrente: un formato che cambia con
    l'orologio non è una funzione pura del dato, e lo stesso Conflitto
    produrrebbe due testi diversi a seconda di quando lo si consegna.
    """
    ultima_notte = check_out - timedelta(days=1)
    if ultima_notte < check_in:
        raise ValueError(f"intervallo senza notti: [{check_in}, {check_out})")
    if check_in.year != ultima_notte.year:
        return (
            f"{check_in.day} {_mese(check_in)} {check_in.year} - "
            f"{ultima_notte.day} {_mese(ultima_notte)} {ultima_notte.year}"
        )
    if check_in == ultima_notte:
        return f"{check_in.day} {_mese(check_in)}"
    if check_in.month == ultima_notte.month:
        return f"{check_in.day}-{ultima_notte.day} {_mese(check_in)}"
    return (
        f"{check_in.day} {_mese(check_in)} - {ultima_notte.day} {_mese(ultima_notte)}"
    )
