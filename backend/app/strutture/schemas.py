"""Schemi API di `strutture` (Pydantic v2)."""

import uuid

from pydantic import BaseModel, Field, computed_field

from app.strutture.models import StatoStruttura
from app.strutture.regime_fiscale import StatoRegime


class StrutturaInput(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    comune: str = Field(min_length=1, max_length=120)
    regione: str = Field(min_length=1, max_length=80)
    cin: str | None = Field(default=None, max_length=30)
    comune_codice_istat: str | None = Field(default=None, max_length=6)


class StrutturaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    comune: str | None = Field(default=None, min_length=1, max_length=120)
    regione: str | None = Field(default=None, min_length=1, max_length=80)
    cin: str | None = Field(default=None, max_length=30)
    comune_codice_istat: str | None = Field(default=None, max_length=6)


class RegimeFiscaleOutput(BaseModel):
    """Contenuto informativo con disclaimer: mai un calcolo d'imposta."""

    stato: StatoRegime
    strutture_non_archiviate: int
    soglia: int | None
    oltre_soglia: bool
    regime: str | None
    testo: str
    aliquote_citate: str | None
    disclaimer: str
    mostra_pannello_transizione: bool

    model_config = {"from_attributes": True}


class StrutturaOutput(BaseModel):
    id: uuid.UUID
    nome: str
    comune: str
    regione: str
    cin: str | None
    stato: StatoStruttura
    comune_codice_istat: str | None
    regione_codice_istat: str | None

    model_config = {"from_attributes": True}

    # Indicatore non bloccante "CIN mancante" (FR-1, UJ-1); l'ignore è il
    # workaround documentato per mypy + computed_field.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cin_mancante(self) -> bool:
        return self.cin is None
