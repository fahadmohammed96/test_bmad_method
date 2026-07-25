"""Entità di `config_normativa` (AD-9, AD-18)."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.date_range import utcnow
from app.core.db import Base, new_uuid7


class Periodicita(enum.Enum):
    MENSILE = "mensile"
    TRIMESTRALE = "trimestrale"
    SEMESTRALE = "semestrale"
    ANNUALE = "annuale"


class Regione(Base):
    """Anagrafica delle Regioni, seedata dai codici ISTAT."""

    __tablename__ = "regione"

    codice_istat: Mapped[str] = mapped_column(String(2), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)


class Comune(Base):
    """Anagrafica dei Comuni, importata dal file ufficiale ISTAT."""

    __tablename__ = "comune"

    codice_istat: Mapped[str] = mapped_column(String(6), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provincia: Mapped[str] = mapped_column(String(4), nullable=False)
    regione_codice_istat: Mapped[str] = mapped_column(
        ForeignKey("regione.codice_istat"), nullable=False, index=True
    )


class ComuneConfig(Base):
    """Parametri della Tassa di soggiorno per Comune, a validità temporale."""

    __tablename__ = "comune_config"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    comune_codice_istat: Mapped[str] = mapped_column(
        ForeignKey("comune.codice_istat"), nullable=False, index=True
    )
    tassa_importo_cent: Mapped[int] = mapped_column(Integer, nullable=False)
    tassa_periodicita: Mapped[Periodicita] = mapped_column(
        Enum(
            Periodicita,
            name="periodicita",
            values_callable=lambda e: [p.value for p in e],
        ),
        nullable=False,
    )
    esenzione_eta_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    esenzione_notti_oltre: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valido_dal: Mapped[date] = mapped_column(Date, nullable=False)
    valido_al: Mapped[date | None] = mapped_column(Date, nullable=True)
    creato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class RegioneConfig(Base):
    """Parametri ISTAT/ROSS1000 per Regione, a validità temporale."""

    __tablename__ = "regione_config"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    regione_codice_istat: Mapped[str] = mapped_column(
        ForeignKey("regione.codice_istat"), nullable=False, index=True
    )
    istat_tracciato: Mapped[str] = mapped_column(String(80), nullable=False)
    istat_periodicita: Mapped[Periodicita] = mapped_column(
        Enum(
            Periodicita,
            name="periodicita",
            values_callable=lambda e: [p.value for p in e],
            create_type=False,
        ),
        nullable=False,
    )
    valido_dal: Mapped[date] = mapped_column(Date, nullable=False)
    valido_al: Mapped[date | None] = mapped_column(Date, nullable=True)
    creato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class ConfigAudit(Base):
    """Registro append-only di chi/cosa/quando sulle modifiche di configurazione."""

    __tablename__ = "config_audit"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_uuid7)
    attore: Mapped[str] = mapped_column(String(200), nullable=False)
    entita: Mapped[str] = mapped_column(String(40), nullable=False)
    entita_riferimento: Mapped[str] = mapped_column(String(20), nullable=False)
    dati: Mapped[dict] = mapped_column(JSONB, nullable=False)
    creato_il: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
