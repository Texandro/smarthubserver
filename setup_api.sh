#!/bin/bash
# Smarthub API — setup complet
set -e
echo '🚀 Installation Smarthub API...'

cat > /srv/smarthub/api/requirements.txt << 'HEREDOC'
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
asyncpg==0.29.0
alembic==1.13.3
pydantic==2.9.2
pydantic-settings==2.5.2
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.12
httpx==0.27.2

HEREDOC

cat > /srv/smarthub/api/Dockerfile << 'HEREDOC'
FROM python:3.12-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

HEREDOC

cat > /srv/smarthub/api/app/__init__.py << 'HEREDOC'

HEREDOC

cat > /srv/smarthub/api/app/core/__init__.py << 'HEREDOC'

HEREDOC

cat > /srv/smarthub/api/app/models/__init__.py << 'HEREDOC'
from .client import Client, Site, Contact
from .timetrack import TimeSession, SessionReport

__all__ = ["Client", "Site", "Contact", "TimeSession", "SessionReport"]

HEREDOC

cat > /srv/smarthub/api/app/routers/__init__.py << 'HEREDOC'
from . import clients, timetrack

HEREDOC

cat > /srv/smarthub/api/app/schemas/__init__.py << 'HEREDOC'

HEREDOC

cat > /srv/smarthub/api/app/services/__init__.py << 'HEREDOC'

HEREDOC

cat > /srv/smarthub/api/app/core/config.py << 'HEREDOC'
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Base
    app_name: str = "Smarthub API"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str

    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480  # 8h — journée de travail

    # CORS — Electron tourne en local
    allowed_origins: list[str] = ["http://localhost:3000", "app://.", "http://localhost:5173"]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()

HEREDOC

cat > /srv/smarthub/api/app/core/database.py << 'HEREDOC'
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import get_settings

settings = get_settings()

# Convertit postgresql:// en postgresql+asyncpg://
db_url = settings.database_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    db_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

HEREDOC

cat > /srv/smarthub/api/app/main.py << 'HEREDOC'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import get_settings
from .routers import clients, timetrack

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"🚀 {settings.app_name} v{settings.app_version} démarré")
    yield
    # Shutdown
    print("👋 Arrêt propre")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API backend du Smarthub — ERP Smartclick BV",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS — Electron + browser local
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(clients.router, prefix="/api/v1")
app.include_router(timetrack.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root():
    return {"message": "Smarthub API", "docs": "/docs"}

HEREDOC

cat > /srv/smarthub/api/app/models/client.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, Numeric, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base
import enum


class ClientStatus(str, enum.Enum):
    actif = "actif"
    dormant = "dormant"
    inactif = "inactif"
    contentieux = "contentieux"
    décédé = "décédé"


class ClientType(str, enum.Enum):
    entreprise = "entreprise"
    asbl = "asbl"
    particulier = "particulier"
    interne = "interne"


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[ClientStatus] = mapped_column(
        Enum(ClientStatus, name="client_status", create_type=False),
        nullable=False,
        default=ClientStatus.actif
    )
    client_type: Mapped[ClientType] = mapped_column(
        Enum(ClientType, name="client_type", create_type=False),
        nullable=False,
        default=ClientType.entreprise
    )
    vat_number: Mapped[str | None] = mapped_column(String(30), unique=True)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    email: Mapped[str | None] = mapped_column(String(200))
    nas_path: Mapped[str | None] = mapped_column(String(500))
    falco_customer_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    notes: Mapped[str | None] = mapped_column(Text)
    inactive_reason: Mapped[str | None] = mapped_column(Text)
    outstanding_debt: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    sites: Mapped[list["Site"]] = relationship("Site", back_populates="client", cascade="all, delete-orphan")
    contacts: Mapped[list["Contact"]] = relationship("Contact", back_populates="client", cascade="all, delete-orphan")
    contracts: Mapped[list["Contract"]] = relationship("Contract", back_populates="client")
    time_sessions: Mapped[list["TimeSession"]] = relationship("TimeSession", back_populates="client")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    nas_path: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    client: Mapped["Client"] = relationship("Client", back_populates="sites")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str | None] = mapped_column(String(100))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    client: Mapped["Client"] = relationship("Client", back_populates="contacts")

HEREDOC

cat > /srv/smarthub/api/app/models/timetrack.py << 'HEREDOC'
from sqlalchemy import String, Text, Boolean, Numeric, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base


class TimeSession(Base):
    __tablename__ = "time_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"))
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))
    activity: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    # duration_minutes et amount sont des colonnes GENERATED — on ne les écrit pas, on les lit seulement
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_included_in_contract: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hourly_rate_applied: Mapped[float | None] = mapped_column(Numeric(8, 2))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    client: Mapped["Client"] = relationship("Client", back_populates="time_sessions")
    report: Mapped["SessionReport | None"] = relationship("SessionReport", back_populates="session", uselist=False)


class SessionReport(Base):
    __tablename__ = "session_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("time_sessions.id", ondelete="CASCADE"), unique=True, nullable=False)
    work_done: Mapped[str] = mapped_column(Text, nullable=False)
    work_pending: Mapped[str | None] = mapped_column(Text)
    blockers: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(Text)
    client_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relations
    session: Mapped["TimeSession"] = relationship("TimeSession", back_populates="report")

HEREDOC

cat > /srv/smarthub/api/app/routers/clients.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from uuid import UUID
from typing import Optional

from ..core.database import get_db
from ..models.client import Client, Site, Contact, ClientStatus
from ..schemas.client import (
    ClientCreate, ClientUpdate, ClientOut, ClientDetail, ClientSummary,
    SiteCreate, SiteUpdate, SiteOut,
    ContactCreate, ContactOut
)

router = APIRouter(prefix="/clients", tags=["clients"])


# ── CLIENTS ───────────────────────────────────────────────

@router.get("/", response_model=list[ClientOut])
async def list_clients(
    status: Optional[ClientStatus] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Liste tous les clients avec filtres optionnels."""
    query = select(Client)
    if status:
        query = query.where(Client.status == status)
    if search:
        query = query.where(
            or_(
                Client.name.ilike(f"%{search}%"),
                Client.vat_number.ilike(f"%{search}%"),
                Client.email.ilike(f"%{search}%"),
            )
        )
    query = query.order_by(Client.name).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/summary", response_model=list[ClientSummary])
async def list_clients_summary(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Version légère pour les dropdowns dans l'overlay et les formulaires."""
    query = select(Client).order_by(Client.name)
    if active_only:
        query = query.where(Client.status == ClientStatus.actif)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientDetail)
async def get_client(client_id: UUID, db: AsyncSession = Depends(get_db)):
    """Détail complet d'un client avec sites et contacts."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    return client


@router.post("/", response_model=ClientOut, status_code=201)
async def create_client(data: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(**data.model_dump())
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(client_id: UUID, data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(client, key, value)
    await db.flush()
    await db.refresh(client)
    return client


# ── SITES ─────────────────────────────────────────────────

@router.get("/{client_id}/sites", response_model=list[SiteOut])
async def list_sites(client_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Site).where(Site.client_id == client_id))
    return result.scalars().all()


@router.post("/{client_id}/sites", response_model=SiteOut, status_code=201)
async def create_site(client_id: UUID, data: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(client_id=client_id, **data.model_dump())
    db.add(site)
    await db.flush()
    await db.refresh(site)
    return site


@router.patch("/{client_id}/sites/{site_id}", response_model=SiteOut)
async def update_site(client_id: UUID, site_id: UUID, data: SiteUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Site).where(Site.id == site_id, Site.client_id == client_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site introuvable")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(site, key, value)
    await db.flush()
    await db.refresh(site)
    return site


# ── CONTACTS ──────────────────────────────────────────────

@router.get("/{client_id}/contacts", response_model=list[ContactOut])
async def list_contacts(client_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contact).where(Contact.client_id == client_id))
    return result.scalars().all()


@router.post("/{client_id}/contacts", response_model=ContactOut, status_code=201)
async def create_contact(client_id: UUID, data: ContactCreate, db: AsyncSession = Depends(get_db)):
    contact = Contact(client_id=client_id, **data.model_dump())
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return contact

HEREDOC

cat > /srv/smarthub/api/app/routers/timetrack.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone
from typing import Optional

from ..core.database import get_db
from ..models.timetrack import TimeSession, SessionReport
from ..models.client import Client
from ..schemas.timetrack import (
    TimeSessionCreate, TimeSessionStop, TimeSessionOut, ActiveSession,
    SessionReportCreate, SessionReportOut
)

router = APIRouter(prefix="/timetrack", tags=["timetrack"])


# ── SESSIONS ──────────────────────────────────────────────

@router.get("/active", response_model=Optional[ActiveSession])
async def get_active_session(db: AsyncSession = Depends(get_db)):
    """Session en cours — endpoint principal de l'overlay."""
    result = await db.execute(
        select(TimeSession, Client.name.label("client_name"))
        .join(Client, TimeSession.client_id == Client.id)
        .where(TimeSession.ended_at.is_(None))
        .order_by(TimeSession.started_at.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    session, client_name = row
    # Calcul durée en live
    now = datetime.now(timezone.utc)
    duration = int((now - session.started_at.replace(tzinfo=timezone.utc)).total_seconds() / 60)
    return ActiveSession(
        id=session.id,
        client_id=session.client_id,
        client_name=client_name,
        activity=session.activity,
        started_at=session.started_at,
        duration_minutes=duration,
    )


@router.post("/start", response_model=TimeSessionOut, status_code=201)
async def start_session(data: TimeSessionCreate, db: AsyncSession = Depends(get_db)):
    """Démarre une nouvelle session. Stop automatiquement toute session active."""
    # Stop session active si elle existe
    active = await db.execute(
        select(TimeSession).where(TimeSession.ended_at.is_(None))
    )
    for s in active.scalars().all():
        s.ended_at = datetime.now(timezone.utc)

    session = TimeSession(
        **data.model_dump(),
        started_at=data.started_at or datetime.now(timezone.utc)
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


@router.post("/{session_id}/stop", response_model=TimeSessionOut)
async def stop_session(
    session_id: UUID,
    data: TimeSessionStop,
    db: AsyncSession = Depends(get_db)
):
    """Stoppe une session et enregistre optionnellement un rapport de fin."""
    result = await db.execute(
        select(TimeSession)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    if session.ended_at:
        raise HTTPException(status_code=400, detail="Session déjà terminée")

    session.ended_at = data.ended_at or datetime.now(timezone.utc)

    if data.report:
        report = SessionReport(
            session_id=session.id,
            **data.report.model_dump()
        )
        db.add(report)

    await db.flush()
    await db.refresh(session)
    return session


@router.get("/sessions", response_model=list[TimeSessionOut])
async def list_sessions(
    client_id: Optional[UUID] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Historique des sessions."""
    query = (
        select(TimeSession)
        .options(selectinload(TimeSession.report))
        .order_by(TimeSession.started_at.desc())
        .limit(limit)
    )
    if client_id:
        query = query.where(TimeSession.client_id == client_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/sessions/{session_id}", response_model=TimeSessionOut)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(TimeSession)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return session


# ── RAPPORT DE SESSION ────────────────────────────────────

@router.post("/sessions/{session_id}/report", response_model=SessionReportOut, status_code=201)
async def add_session_report(
    session_id: UUID,
    data: SessionReportCreate,
    db: AsyncSession = Depends(get_db)
):
    """Ajoute un rapport à une session existante."""
    result = await db.execute(select(TimeSession).where(TimeSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    existing = await db.execute(select(SessionReport).where(SessionReport.session_id == session_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Cette session a déjà un rapport")

    report = SessionReport(session_id=session_id, **data.model_dump())
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


# ── TODAY SUMMARY ─────────────────────────────────────────

@router.get("/today", response_model=dict)
async def today_summary(db: AsyncSession = Depends(get_db)):
    """Résumé de la journée — pour le dashboard et l'overlay."""
    result = await db.execute(text("""
        SELECT
            COUNT(*)                                    AS session_count,
            COALESCE(SUM(duration_minutes), 0)          AS total_minutes,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_amount,
            COUNT(CASE WHEN ended_at IS NULL THEN 1 END) AS active_sessions
        FROM time_sessions
        WHERE started_at::date = CURRENT_DATE
    """))
    row = result.mappings().first()
    return {
        "session_count": row["session_count"],
        "total_hours": round(row["total_minutes"] / 60, 2) if row["total_minutes"] else 0,
        "billable_amount": float(row["billable_amount"]) if row["billable_amount"] else 0,
        "active_sessions": row["active_sessions"],
    }

HEREDOC

cat > /srv/smarthub/api/app/schemas/client.py << 'HEREDOC'
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

HEREDOC

cat > /srv/smarthub/api/app/schemas/timetrack.py << 'HEREDOC'
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

HEREDOC

echo '✅ Tous les fichiers créés!'
