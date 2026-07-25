"""Repository di `identity`: nessuna query di dominio fuori da qui (AD-2)."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.identity.models import Host, Sessione, TentativoLogin


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


class TentativoLoginRepository:
    """Tracce dei tentativi di accesso: pre-autenticazione, non tenant-owned."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def registra(self, email: str, origine: str) -> None:
        self._db.add(TentativoLogin(email=email, origine=origine))

    def conta_per_email(self, email: str, dal: datetime) -> int:
        return self._conta(TentativoLogin.email == email, dal)

    def conta_per_origine(self, origine: str, dal: datetime) -> int:
        return self._conta(TentativoLogin.origine == origine, dal)

    def _conta(self, condizione, dal: datetime) -> int:
        return int(
            self._db.scalar(
                select(func.count())
                .select_from(TentativoLogin)
                .where(condizione, TentativoLogin.avvenuto_il >= dal)
            )
            or 0
        )

    def azzera_per_email(self, email: str) -> None:
        """Un accesso riuscito cancella il debito dell'account."""
        self._db.execute(delete(TentativoLogin).where(TentativoLogin.email == email))


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

    def delete_altre_dell_host(self, host_id: uuid.UUID, token_hash: str) -> None:
        """Elimina tutte le sessioni dell'Host tranne quella corrente."""
        self._db.execute(
            delete(Sessione).where(
                Sessione.host_id == host_id, Sessione.token_hash != token_hash
            )
        )
