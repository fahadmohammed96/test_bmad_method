"""Repository di `identity`: nessuna query di dominio fuori da qui (AD-2)."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.models import Host, Sessione


class HostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def by_email(self, email: str) -> Host | None:
        return self._db.scalars(select(Host).where(Host.email == email)).one_or_none()

    def by_id(self, host_id: uuid.UUID) -> Host | None:
        return self._db.get(Host, host_id)

    def add(self, host: Host) -> Host:
        self._db.add(host)
        return host


class SessioneRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, sessione: Sessione) -> Sessione:
        self._db.add(sessione)
        return sessione

    def valida_by_token_hash(self, token_hash: str, now: datetime) -> Sessione | None:
        return self._db.scalars(
            select(Sessione).where(
                Sessione.token_hash == token_hash, Sessione.expires_at > now
            )
        ).one_or_none()

    def delete(self, sessione: Sessione) -> None:
        self._db.delete(sessione)
