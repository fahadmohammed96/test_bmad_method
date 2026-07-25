"""Service di `identity` (AD-15): registrazione, login, sessioni.

Password con argon2id; token di sessione opachi, persistiti solo come
hash SHA-256; scadenza fissa configurabile. Le mutazioni di stato di
host/sessione avvengono SOLO qui (AD-18).
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.date_range import utcnow
from app.identity.models import Host, Sessione
from app.identity.repository import HostRepository, SessioneRepository

_hasher = PasswordHasher()  # profilo argon2id di default della libreria

# Hash fittizio per pareggiare i tempi del login con email sconosciuta
# (nessuna enumerazione utenti via timing).
_DUMMY_HASH = _hasher.hash("password-fittizia-anti-enumerazione")


class EmailGiaRegistrataError(Exception):
    pass


class CredenzialiNonValideError(Exception):
    pass


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
    db.flush()
    token = _apri_sessione(db, host)
    db.commit()
    return SessioneAperta(host=host, token=token)


def login(db: Session, email: str, password: str) -> SessioneAperta:
    email = _normalizza_email(email)
    host = HostRepository(db).by_email(email)
    try:
        _hasher.verify(host.password_hash if host else _DUMMY_HASH, password)
    except VerificationError:
        raise CredenzialiNonValideError() from None
    if host is None:
        raise CredenzialiNonValideError()
    token = _apri_sessione(db, host)
    db.commit()
    return SessioneAperta(host=host, token=token)


def host_da_token(db: Session, token: str) -> Host | None:
    sessione = SessioneRepository(db).valida_by_token_hash(
        _token_hash(token), now=utcnow()
    )
    if sessione is None:
        return None
    return HostRepository(db).by_id(sessione.host_id)


def logout(db: Session, token: str) -> None:
    sessioni = SessioneRepository(db)
    sessione = sessioni.valida_by_token_hash(_token_hash(token), now=utcnow())
    if sessione is not None:
        sessioni.delete(sessione)
        db.commit()
