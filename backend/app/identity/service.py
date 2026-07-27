"""Service di `identity` (AD-15): registrazione, login, sessioni.

Password con argon2id; token di sessione opachi, persistiti solo come
hash SHA-256; scadenza fissa configurabile. Le mutazioni di stato di
host/sessione avvengono SOLO qui (AD-18).
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.date_range import utcnow
from app.identity.models import CanaleNotifica, Host, Sessione
from app.identity.repository import (
    HostRepository,
    SessioneRepository,
    TentativoLoginRepository,
)

_hasher = PasswordHasher()  # profilo argon2id di default della libreria

# Hash fittizio per pareggiare i tempi del login con email sconosciuta
# (nessuna enumerazione utenti via timing).
_DUMMY_HASH = _hasher.hash("password-fittizia-anti-enumerazione")


class EmailGiaRegistrataError(Exception):
    pass


class HostNonTrovatoError(Exception):
    pass


class CredenzialiNonValideError(Exception):
    pass


class TroppiTentativiError(Exception):
    """Freno agli accessi ripetuti: temporaneo, mai un lockout definitivo."""

    def __init__(self, riprova_fra_secondi: int) -> None:
        super().__init__("troppi tentativi di accesso")
        self.riprova_fra_secondi = riprova_fra_secondi


@dataclass(frozen=True, slots=True)
class SessioneAperta:
    host: Host
    token: str


def _normalizza_email(email: str) -> str:
    return email.strip().lower()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _apri_sessione(db: Session, host: Host) -> str:
    token = secrets.token_urlsafe(32)
    SessioneRepository(db).add(
        Sessione(
            host_id=host.id,
            token_hash=_token_hash(token),
            expires_at=utcnow() + timedelta(days=get_settings().session_ttl_days),
        )
    )
    return token


def registra_host(db: Session, email: str, password: str) -> SessioneAperta:
    email = _normalizza_email(email)
    hosts = HostRepository(db)
    if hosts.by_email(email) is not None:
        raise EmailGiaRegistrataError(email)
    host = hosts.add(Host(email=email, password_hash=_hasher.hash(password)))
    try:
        db.flush()
    except IntegrityError:
        # Gara tra registrazioni sulla stessa email (G-2): il pre-check è
        # passato in entrambe, decide il vincolo UNIQUE del DB → 409, non 500.
        db.rollback()
        raise EmailGiaRegistrataError(email) from None
    token = _apri_sessione(db, host)
    db.commit()
    return SessioneAperta(host=host, token=token)


def _verifica_freno(db: Session, email: str, origine: str) -> None:
    """Freno agli accessi ripetuti (G-5).

    Due limiti su finestra temporale: per account (Host preso di mira) e
    per origine (spraying su molti account). Si applica PRIMA di guardare
    le credenziali e vale anche per email inesistenti, altrimenti la
    differenza di comportamento rivelerebbe quali account esistono.
    """
    settings = get_settings()
    tentativi = TentativoLoginRepository(db)
    dal = utcnow() - timedelta(minutes=settings.login_finestra_minuti)

    per_account = tentativi.conta_per_email(email, dal)
    per_origine = tentativi.conta_per_origine(origine, dal)
    if (
        per_account >= settings.login_max_tentativi_account
        or per_origine >= settings.login_max_tentativi_origine
    ):
        raise TroppiTentativiError(settings.login_finestra_minuti * 60)


def login(
    db: Session, email: str, password: str, origine: str = "sconosciuta"
) -> SessioneAperta:
    email = _normalizza_email(email)
    _verifica_freno(db, email, origine)

    host = HostRepository(db).by_email(email)
    try:
        _hasher.verify(host.password_hash if host else _DUMMY_HASH, password)
        credenziali_valide = host is not None
    except VerificationError:
        credenziali_valide = False

    if not credenziali_valide or host is None:
        TentativoLoginRepository(db).registra(email, origine)
        db.commit()
        raise CredenzialiNonValideError()

    # L'accesso riuscito cancella il debito dell'account.
    TentativoLoginRepository(db).azzera_per_email(email)
    token = _apri_sessione(db, host)
    db.commit()
    return SessioneAperta(host=host, token=token)


def leggi_host(db: Session, host_id: uuid.UUID) -> Host:
    """L'Host, per gli altri moduli. Solleva se non esiste (AD-18).

    `identity` è il proprietario di `host`: chi ha bisogno di sapere se un
    Host esiste — per esempio l'endpoint interno che azzera tutti i suoi
    Ospiti su richiesta — passa di qui e non dalla tabella. Senza questa
    domanda un `host_id` inesistente non produrrebbe un errore ma un
    azzeramento riuscito su zero righe, cioè una richiesta GDPR dichiarata
    evasa e mai evasa.
    """
    host = HostRepository(db).by_id(host_id)
    if host is None:
        raise HostNonTrovatoError()
    return host


def host_da_token(db: Session, token: str) -> Host | None:
    sessione = SessioneRepository(db).valida_by_token_hash(
        _token_hash(token), now=utcnow()
    )
    if sessione is None:
        return None
    return HostRepository(db).by_id(sessione.host_id)


def aggiorna_preferenze(db: Session, host: Host, canale: CanaleNotifica) -> Host:
    host.canale_notifica_preferito = canale
    db.commit()
    return host


def cambia_password(
    db: Session, host: Host, password_attuale: str, password_nuova: str, token: str
) -> None:
    """Ruota la password e invalida ogni altra sessione dell'Host."""
    try:
        _hasher.verify(host.password_hash, password_attuale)
    except VerificationError:
        raise CredenzialiNonValideError() from None
    host.password_hash = _hasher.hash(password_nuova)
    SessioneRepository(db).delete_altre_dell_host(host.id, _token_hash(token))
    db.commit()


def logout(db: Session, token: str) -> None:
    sessioni = SessioneRepository(db)
    sessione = sessioni.valida_by_token_hash(_token_hash(token), now=utcnow())
    if sessione is not None:
        sessioni.delete(sessione)
        db.commit()
