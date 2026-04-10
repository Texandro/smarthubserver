from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from typing import Optional
from app.models.client import ClientStatus, ClientType


# ── Site ──────────────────────────────────────────────────

class SiteBase(BaseModel):
    name: str
    address: Optional[str] = None
    nas_path: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None

class SiteCreate(SiteBase):
    pass

class SiteUpdate(SiteBase):
    name: Optional[str] = None

class SiteOut(SiteBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Contact ───────────────────────────────────────────────

class ContactBase(BaseModel):
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None
    site_id: Optional[UUID] = None

class ContactCreate(ContactBase):
    pass

class ContactOut(ContactBase):
    id: UUID
    client_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Client ────────────────────────────────────────────────

class ClientBase(BaseModel):
    name: str
    status: ClientStatus = ClientStatus.actif
    client_type: ClientType = ClientType.entreprise
    vat_number: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    nas_path: Optional[str] = None
    falco_customer_id: Optional[str] = None
    notes: Optional[str] = None
    inactive_reason: Optional[str] = None
    outstanding_debt: float = 0

class ClientCreate(ClientBase):
    pass

class ClientUpdate(ClientBase):
    name: Optional[str] = None
    status: Optional[ClientStatus] = None
    client_type: Optional[ClientType] = None

class ClientOut(ClientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class ClientDetail(ClientOut):
    sites: list[SiteOut] = []
    contacts: list[ContactOut] = []

class ClientSummary(BaseModel):
    """Version légère pour les dropdowns et listes"""
    id: UUID
    name: str
    status: ClientStatus
    client_type: ClientType
    model_config = {"from_attributes": True}

