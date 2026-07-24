"""Schemi API di `identity` (input validati al confine, Pydantic v2)."""

import uuid

from pydantic import BaseModel, EmailStr, Field


class CredenzialiInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class HostOutput(BaseModel):
    id: uuid.UUID
    email: str

    model_config = {"from_attributes": True}
