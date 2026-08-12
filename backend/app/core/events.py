"""Catalogo unico versionato di eventi di dominio e job (AD-17).

Ogni tipo è dichiarato qui con nome `<entita>.<fatto_passato>` e schema del
payload. Il payload porta SOLO identificatori e il fatto (mai snapshot di
stato): il consumatore rilegge lo stato corrente via interfacce di service.
"""

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

CATALOG_VERSION = 1

_TYPE_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")

_SCALAR_TYPES = (str, int, bool, type(None))


class CatalogError(Exception):
    """Errore del catalogo eventi/job."""


class InvalidTypeNameError(CatalogError):
    """Il nome non rispetta la convenzione `<entita>.<fatto_passato>`."""


class DuplicateTypeError(CatalogError):
    """Tipo già dichiarato nel catalogo."""


class UnknownTypeError(CatalogError):
    """Tipo non dichiarato nel catalogo."""


class PayloadValidationError(CatalogError):
    """Il payload non rispetta lo schema dichiarato (soli identificatori)."""


@dataclass(frozen=True, slots=True)
class MessageType:
    name: str
    payload_keys: frozenset[str]


def _validate_payload(tipo: MessageType, payload: Mapping[str, object]) -> None:
    keys = frozenset(payload.keys())
    if keys != tipo.payload_keys:
        raise PayloadValidationError(
            f"{tipo.name}: chiavi {sorted(keys)} != schema {sorted(tipo.payload_keys)}"
        )
    for key, value in payload.items():
        if not isinstance(value, _SCALAR_TYPES):
            raise PayloadValidationError(
                f"{tipo.name}: '{key}' non è un identificatore scalare "
                "(vietati snapshot di stato nel payload)"
            )


class Catalog:
    """Registro esplicito dei tipi di evento e di job."""

    def __init__(self) -> None:
        self._events: dict[str, MessageType] = {}
        self._jobs: dict[str, MessageType] = {}

    @staticmethod
    def _new_type(name: str, payload_keys: Iterable[str]) -> MessageType:
        if not _TYPE_NAME_RE.match(name):
            raise InvalidTypeNameError(
                f"'{name}' non rispetta la convenzione <entita>.<fatto_passato>"
            )
        return MessageType(name=name, payload_keys=frozenset(payload_keys))

    def register_event(self, name: str, payload_keys: Iterable[str]) -> MessageType:
        tipo = self._new_type(name, payload_keys)
        if name in self._events:
            raise DuplicateTypeError(f"evento '{name}' già dichiarato")
        self._events[name] = tipo
        return tipo

    def register_job(self, name: str, payload_keys: Iterable[str]) -> MessageType:
        tipo = self._new_type(name, payload_keys)
        if name in self._jobs:
            raise DuplicateTypeError(f"job '{name}' già dichiarato")
        self._jobs[name] = tipo
        return tipo

    def event(self, name: str) -> MessageType:
        try:
            return self._events[name]
        except KeyError:
            raise UnknownTypeError(f"evento '{name}' non a catalogo") from None

    def job(self, name: str) -> MessageType:
        try:
            return self._jobs[name]
        except KeyError:
            raise UnknownTypeError(f"job '{name}' non a catalogo") from None

    def event_names(self) -> tuple[str, ...]:
        return tuple(self._events)

    def job_names(self) -> tuple[str, ...]:
        return tuple(self._jobs)

    def validate_event_payload(self, name: str, payload: Mapping[str, object]) -> None:
        _validate_payload(self.event(name), payload)

    def validate_job_payload(self, name: str, payload: Mapping[str, object]) -> None:
        _validate_payload(self.job(name), payload)


# Catalogo di produzione: i tipi si dichiarano qui, Story per Story,
# nel momento in cui il modulo proprietario li emette per la prima volta.
catalog = Catalog()

# strutture (Story 1.4) — proprietario: modulo `strutture`.
catalog.register_event("struttura.creata", payload_keys=("struttura_id", "host_id"))
catalog.register_event("struttura.archiviata", payload_keys=("struttura_id", "host_id"))
# Regime fiscale (Story 1.6): si emette la TRANSIZIONE di soglia, non lo
# stato — il Regime resta derivato alla lettura (AD-12).
catalog.register_event(
    "regime_fiscale.soglia_superata", payload_keys=("host_id", "conteggio")
)
catalog.register_event(
    "regime_fiscale.rientrato", payload_keys=("host_id", "conteggio")
)
# calendario (Story 2.4, esteso dalla 2.5) — proprietario: modulo `calendario`.
#
# `prenotazione.cessata` è l'evento dell'USCITA dallo stato `attiva` (AD-19),
# e le uscite sono TRE — non solo la cancellazione manuale dell'Host:
#
#   1. l'Host cancella una Prenotazione manuale   `attiva → cancellata`
#   2. l'evento scompare dal feed                 `attiva → rimossa_dal_feed`
#   3. il feed la dà `STATUS:CANCELLED`           `attiva → cancellata`
#
# Fino alla Story 2.4 lo emetteva solo la prima, e il nome prometteva più di
# quanto il catalogo mantenesse: chi legge questa riga per implementare un
# consumatore trova un evento che SEMBRA coprire i tre casi. Dalla decisione
# MYL-69 (opzione A) lo emettono tutte e tre, e il consumatore ne ascolta uno
# solo — il caso più frequente nella vita reale è il secondo, perché le
# disdette arrivano dai portali, non dall'Host.
#
# La `struttura_id` viaggia col fatto perché la rilevazione dei Conflitti è
# scopata alla Struttura, e senza quell'identificatore il consumatore dovrebbe
# rileggere la Prenotazione solo per sapere dove guardare.
#
# SOLI identificatori: né il `sommario`, né il nome dell'Ospite. La tabella
# `outbox` è append-only e leggibile da chi amministra il sistema, quindi un
# dato personale scritto qui **sopravvivrebbe** alla retention che AD-21 gli
# impone (AD-16, AD-17, NFR-11).
catalog.register_event(
    "prenotazione.cessata",
    payload_keys=("prenotazione_id", "host_id", "struttura_id"),
)
# Conflitti (Story 2.5, AD-5). Due fatti e non uno stato: SM-C1 distingue i
# Conflitti che l'Host ha davvero risolto (`gestito`, Story 2.7) da quelli che
# si sono spenti da soli perché una Prenotazione è uscita da `attiva`
# (`decaduto`), e AD-16 vuole che le metriche si misurino dagli eventi di
# dominio senza strumentazione separata. Con un solo evento «conflitto
# cambiato» quella distinzione andrebbe cercata rileggendo lo stato corrente,
# che al momento della misura è già l'ultimo e non dice come ci si è arrivati.
catalog.register_event(
    "conflitto.rilevato", payload_keys=("conflitto_id", "host_id", "struttura_id")
)
catalog.register_event(
    "conflitto.decaduto", payload_keys=("conflitto_id", "host_id", "struttura_id")
)
