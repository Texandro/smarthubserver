import uuid
import enum
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from ..core.database import Base


class OnsiteStatus(str, enum.Enum):
    planifiee = "planifiée"
    en_cours  = "en_cours"
    terminee  = "terminée"
    annulee   = "annulée"


class OnSiteIntervention(Base):
    __tablename__ = "on_site_interventions"

    id              : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id       : Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    site_id         : Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"))
    contract_id     : Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"))
    session_id      : Mapped[uuid.UUID|None] = mapped_column(UUID(as_uuid=True), ForeignKey("time_sessions.id", ondelete="SET NULL"))
    titre           : Mapped[str]            = mapped_column(String(300), nullable=False)
    description     : Mapped[str|None]       = mapped_column(Text)
    status          : Mapped[OnsiteStatus]   = mapped_column(Enum(OnsiteStatus, name="onsite_status", create_type=False), nullable=False, default=OnsiteStatus.planifiee)
    planned_at      : Mapped[DateTime|None]  = mapped_column(DateTime(timezone=True))
    started_at      : Mapped[DateTime|None]  = mapped_column(DateTime(timezone=True))
    ended_at        : Mapped[DateTime|None]  = mapped_column(DateTime(timezone=True))
    # elapsed_min est GENERATED ALWAYS — ne pas écrire, lire seulement
    technicien      : Mapped[str]            = mapped_column(String(100), nullable=False, default="Mathieu Pleitinx")
    notes_depart    : Mapped[str|None]       = mapped_column(Text)
    notes_fin       : Mapped[str|None]       = mapped_column(Text)
    materiel_utilise: Mapped[str|None]       = mapped_column(Text)
    is_billable     : Mapped[bool]           = mapped_column(Boolean, nullable=False, default=True)
    pdf_report_path : Mapped[str|None]       = mapped_column(String(500))
    created_at      : Mapped[DateTime]       = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at      : Mapped[DateTime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    client  : Mapped["Client"]  = relationship("Client")
