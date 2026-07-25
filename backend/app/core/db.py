"""Base SQLAlchemy, PK UUIDv7 e sessioni (spine Consistency Conventions)."""

import uuid
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def new_uuid7() -> uuid.UUID:
    """PK UUIDv7 (time-ordered), generate applicativamente."""
    return uuid.uuid7()


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine())


def get_db() -> Iterator[Session]:
    """Dependency FastAPI: una sessione DB per richiesta."""
    with get_sessionmaker()() as session:
        yield session
