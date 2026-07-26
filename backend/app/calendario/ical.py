"""Parser iCal (RFC 5545) — funzione pura su testo, nessun I/O.

Fa una cosa sola e la fa in modo severo: trasforma il corpo di una risposta
in VEVENT grezzi, **oppure** dichiara il feed non valido.

La severità è il punto (E2-G3). Un corpo troncato, vuoto o parziale con esito
200 non deve produrre «un evento in meno»: deve produrre un **errore**.
Altrimenti il chiamante non ha modo di distinguere un errore di trasporto da
un calendario davvero svuotato, e la regola append-preserving («evento
scomparso ⇒ `rimossa_dal_feed`») marcherebbe come rimosse prenotazioni vive.
È la catena che trasforma una connessione chiusa a metà in una doppia
prenotazione non segnalata.
"""

from collections.abc import Mapping
from dataclasses import dataclass

BEGIN_VCALENDAR = "BEGIN:VCALENDAR"
END_VCALENDAR = "END:VCALENDAR"
BEGIN_VEVENT = "BEGIN:VEVENT"
END_VEVENT = "END:VEVENT"


class FeedNonValidoError(ValueError):
    """Il corpo non è un calendario iCal completo e chiuso."""


@dataclass(frozen=True, slots=True)
class Proprieta:
    nome: str
    parametri: Mapping[str, str]
    valore: str


@dataclass(frozen=True, slots=True)
class Vevent:
    proprieta: tuple[Proprieta, ...]

    def prima(self, nome: str) -> Proprieta | None:
        """Prima occorrenza della proprietà, `None` se assente."""
        for proprieta in self.proprieta:
            if proprieta.nome == nome:
                return proprieta
        return None

    def valore(self, nome: str) -> str | None:
        proprieta = self.prima(nome)
        return None if proprieta is None else proprieta.valore

    @property
    def uid(self) -> str | None:
        """`UID` ripulito degli spazi; `None` se assente o vuoto.

        Le maiuscole NON si normalizzano: in iCal l'UID è case-sensitive e
        appiattirlo unirebbe due prenotazioni distinte.
        """
        grezzo = self.valore("UID")
        if grezzo is None:
            return None
        pulito = grezzo.strip()
        return pulito or None


@dataclass(frozen=True, slots=True)
class FeedAnalizzato:
    eventi: tuple[Vevent, ...]


def _decodifica(corpo: bytes | str) -> str:
    if isinstance(corpo, str):
        return corpo.lstrip("﻿")
    # RFC 5545 impone UTF-8; `utf-8-sig` toglie anche il BOM. Un feed che
    # non lo rispetta non deve far cadere il parser: si degrada a latin-1,
    # che non solleva mai, invece di sollevare un 500 su byte inattesi.
    try:
        return corpo.decode("utf-8-sig")
    except UnicodeDecodeError:
        return corpo.decode("latin-1")


def _srotola(testo: str) -> list[str]:
    """Righe logiche: il content line ripiegato si ricompone (RFC 5545 §3.1).

    Una riga che inizia con spazio o tab è la continuazione della precedente:
    il primo carattere è il marcatore di fold e si scarta.
    """
    grezze = testo.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    logiche: list[str] = []
    for riga in grezze:
        if riga[:1] in (" ", "\t") and logiche:
            logiche[-1] += riga[1:]
        else:
            logiche.append(riga)
    return [riga for riga in logiche if riga.strip()]


def _separa_fuori_dagli_apici(riga: str, separatori: str) -> list[str]:
    """Spezza sui separatori che stanno fuori da una stringa fra apici."""
    pezzi: list[str] = []
    corrente: list[str] = []
    fra_apici = False
    for carattere in riga:
        if carattere == '"':
            fra_apici = not fra_apici
            corrente.append(carattere)
        elif carattere in separatori and not fra_apici:
            pezzi.append("".join(corrente))
            corrente = []
        else:
            corrente.append(carattere)
    pezzi.append("".join(corrente))
    return pezzi


def _srotola_escape(valore: str) -> str:
    """Escape TEXT di RFC 5545: `\\n` `\\,` `\\;` `\\\\`."""
    risultato: list[str] = []
    indice = 0
    while indice < len(valore):
        carattere = valore[indice]
        if carattere == "\\" and indice + 1 < len(valore):
            successivo = valore[indice + 1]
            risultato.append("\n" if successivo in ("n", "N") else successivo)
            indice += 2
            continue
        risultato.append(carattere)
        indice += 1
    return "".join(risultato)


def _analizza_proprieta(riga: str) -> Proprieta | None:
    testa, separatore, valore = _spezza_su_due_punti(riga)
    if not separatore:
        return None
    pezzi = _separa_fuori_dagli_apici(testa, ";")
    nome = pezzi[0].strip().upper()
    if not nome:
        return None
    parametri: dict[str, str] = {}
    for pezzo in pezzi[1:]:
        chiave, uguale, valore_parametro = pezzo.partition("=")
        if uguale:
            parametri[chiave.strip().upper()] = valore_parametro.strip().strip('"')
    return Proprieta(nome=nome, parametri=parametri, valore=_srotola_escape(valore))


def _spezza_su_due_punti(riga: str) -> tuple[str, str, str]:
    """Divide `NOME;PARAM=v:valore` sul primo `:` fuori dagli apici.

    Serve perché un parametro fra apici può contenere `:` (per esempio un
    `ALTREP` con un URI): spezzare sul primo `:` assoluto romperebbe la riga.
    """
    fra_apici = False
    for indice, carattere in enumerate(riga):
        if carattere == '"':
            fra_apici = not fra_apici
        elif carattere == ":" and not fra_apici:
            return riga[:indice], ":", riga[indice + 1 :]
    return riga, "", ""


def analizza_feed(corpo: bytes | str) -> FeedAnalizzato:
    """VEVENT del calendario, o `FeedNonValidoError` se il corpo è incompleto.

    Un calendario chiuso senza alcun VEVENT è valido e vuoto: sta al service
    decidere che un feed vuoto non autorizza nessuna transizione di stato.
    """
    righe = _srotola(_decodifica(corpo))
    if not righe:
        raise FeedNonValidoError("corpo vuoto")

    nomi = [riga.strip().upper() for riga in righe]
    if BEGIN_VCALENDAR not in nomi:
        raise FeedNonValidoError("nessun BEGIN:VCALENDAR: il corpo non è un calendario")
    if nomi[-1] != END_VCALENDAR:
        raise FeedNonValidoError(
            "calendario non chiuso da END:VCALENDAR: risposta troncata o parziale"
        )

    eventi: list[Vevent] = []
    corrente: list[Proprieta] | None = None
    for riga, nome in zip(righe, nomi, strict=True):
        if nome == BEGIN_VEVENT:
            if corrente is not None:
                raise FeedNonValidoError("BEGIN:VEVENT annidato")
            corrente = []
            continue
        if nome == END_VEVENT:
            if corrente is None:
                raise FeedNonValidoError("END:VEVENT senza BEGIN:VEVENT")
            eventi.append(Vevent(proprieta=tuple(corrente)))
            corrente = None
            continue
        if corrente is None:
            continue
        proprieta = _analizza_proprieta(riga)
        if proprieta is not None:
            corrente.append(proprieta)

    if corrente is not None:
        raise FeedNonValidoError(
            "VEVENT non chiuso da END:VEVENT: risposta troncata a metà evento"
        )
    return FeedAnalizzato(eventi=tuple(eventi))
