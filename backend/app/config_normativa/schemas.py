"""Schemi API di `config_normativa` (Pydantic v2)."""

from datetime import date

from pydantic import BaseModel, Field

from app.config_normativa.models import Periodicita
from app.config_normativa.service import Motivo, StatoConfigurazione


class RegioneOutput(BaseModel):
    codice_istat: str
    nome: str

    model_config = {"from_attributes": True}


class ComuneOutput(BaseModel):
    codice_istat: str
    nome: str
    provincia: str
    regione_codice_istat: str

    model_config = {"from_attributes": True}


class ParametriTassaOutput(BaseModel):
    importo_cent: int
    periodicita: Periodicita
    esenzione_eta_max: int | None
    esenzione_notti_oltre: int | None


class ParametriIstatOutput(BaseModel):
    tracciato: str
    periodicita: Periodicita


class AreaTassaOutput(BaseModel):
    stato: StatoConfigurazione
    motivo: Motivo | None
    messaggio: str
    promemoria_manuale: bool
    parametri: ParametriTassaOutput | None


class AreaIstatOutput(BaseModel):
    stato: StatoConfigurazione
    motivo: Motivo | None
    messaggio: str
    promemoria_manuale: bool
    parametri: ParametriIstatOutput | None


class ConfigurazioneNormativaOutput(BaseModel):
    alla_data: date
    tassa_soggiorno: AreaTassaOutput
    istat: AreaIstatOutput


class ComuneConfigInput(BaseModel):
    attore: str = Field(min_length=1, max_length=200)
    tassa_importo_cent: int = Field(ge=0)
    tassa_periodicita: Periodicita
    esenzione_eta_max: int | None = Field(default=None, ge=0)
    esenzione_notti_oltre: int | None = Field(default=None, ge=0)
    valido_dal: date
    valido_al: date | None = None


class RegioneConfigInput(BaseModel):
    attore: str = Field(min_length=1, max_length=200)
    istat_tracciato: str = Field(min_length=1, max_length=80)
    istat_periodicita: Periodicita
    valido_dal: date
    valido_al: date | None = None


class ConfigSalvataOutput(BaseModel):
    valido_dal: date
    valido_al: date | None
