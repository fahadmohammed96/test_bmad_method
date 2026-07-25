"""Schemi API di `identity` (input validati al confine, Pydantic v2)."""

import uuid

from pydantic import BaseModel, EmailStr, Field

from app.identity.models import CanaleNotifica


class CredenzialiInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class PreferenzeInput(BaseModel):
    canale_notifica_preferito: CanaleNotifica


class CambioPasswordInput(BaseModel):
    password_attuale: str = Field(max_length=128)
    password_nuova: str = Field(min_length=8, max_length=128)


class HostOutput(BaseModel):
    id: uuid.UUID
    email: str
    canale_notifica_preferito: CanaleNotifica

    model_config = {"from_attributes": True}
