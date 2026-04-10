from pydantic import BaseModel, model_validator
from uuid import UUID
from datetime import datetime
from typing import Optional


class SessionReportBase(BaseModel):
    work_done: str
    work_pending: Optional[str] = None
    blockers: Optional[str] = None
    next_action: Optional[str] = None
    client_notified: bool = False

class SessionReportCreate(SessionReportBase):
    pass

class SessionReportOut(SessionReportBase):
    id: UUID
    session_id: UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class TimeSessionBase(BaseModel):
    client_id: UUID
    site_id: Optional[UUID] = None
    contract_id: Optional[UUID] = None
    project_id: Optional[UUID] = None
    activity: str
    description: Optional[str] = None
    is_billable: bool = True
    is_included_in_contract: bool = False
    hourly_rate_applied: Optional[float] = None
    tags: Optional[list[str]] = None

class TimeSessionCreate(TimeSessionBase):
    started_at: Optional[datetime] = None  # Si None → NOW()

class TimeSessionStop(BaseModel):
    """Pour stopper une session en cours"""
    ended_at: Optional[datetime] = None  # Si None → NOW()
    report: Optional[SessionReportCreate] = None

class TimeSessionOut(TimeSessionBase):
    id: UUID
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None   # Colonne GENERATED
    amount: Optional[float] = None           # Colonne GENERATED
    created_at: datetime
    report: Optional[SessionReportOut] = None
    model_config = {"from_attributes": True}

class ActiveSession(BaseModel):
    """Session en cours — pour l'overlay"""
    id: UUID
    client_id: UUID
    client_name: str
    activity: str
    started_at: datetime
    duration_minutes: Optional[int] = None
    model_config = {"from_attributes": True}

