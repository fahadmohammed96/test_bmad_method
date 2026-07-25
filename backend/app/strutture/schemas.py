"""Schemi API di `strutture` (Pydantic v2)."""

import uuid

from pydantic import BaseModel, Field, computed_field

from app.strutture.models import StatoStruttura


class StrutturaInput(BaseModel):
    nome: str = Field(min_length=1, max_length=200)
    comune: str = Field(min_length=1, max_length=120)
    regione: str = Field(min_length=1, max_length=80)
    cin: str | None = Field(default=None, max_length=30)


class StrutturaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=200)
    comune: str | None = Field(default=None, min_length=1, max_length=120)
    regione: str | None = Field(default=None, min_length=1, max_length=80)
    cin: str | None = Field(default=None, max_length=30)


class StrutturaOutput(BaseModel):
    id: uuid.UUID
    nome: str
    comune: str
    regione: str
    cin: str | None
    stato: StatoStruttura

    model_config = {"from_attributes": True}

    # Indicatore non bloccante "CIN mancante" (FR-1, UJ-1); l'ignore è il
    # workaround documentato per mypy + computed_field.
    @computed_field  # type: ignore[prop-decorator]
    @property
    def cin_mancante(self) -> bool:
        return self.cin is None
