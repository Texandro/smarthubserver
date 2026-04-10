from sqlalchemy import String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base
import enum


class ForensicsStatus(str, enum.Enum):
    ouvert = "ouvert"
    en_cours = "en_cours"
    en_attente = "en_attente"
    clôturé = "clôturé"


class EvidenceType(str, enum.Enum):
    disque_dur = "disque_dur"
    usb = "usb"
    fichier = "fichier"
    email = "email"
    log = "log"
    autre = "autre"


class ForensicsCase(Base):
    __tablename__ = "forensics_cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)

    case_reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    objectives: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str | None] = mapped_column(Text)

    status: Mapped[ForensicsStatus] = mapped_column(
        Enum(ForensicsStatus, name="forensics_status", create_type=False),
        nullable=False, default=ForensicsStatus.ouvert)

    phases_data: Mapped[dict | None] = mapped_column(JSONB, default={})

    opened_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    closed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    final_report_path: Mapped[str | None] = mapped_column(String(500))
    chain_of_custody_notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="forensics_cases")
    evidence: Mapped[list["ForensicsEvidence"]] = relationship("ForensicsEvidence", back_populates="case", cascade="all, delete-orphan")


class ForensicsEvidence(Base):
    __tablename__ = "forensics_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("forensics_cases.id", ondelete="CASCADE"), nullable=False)

    evidence_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[EvidenceType] = mapped_column(Enum(EvidenceType, name="evidence_type", create_type=False), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(200))
    hash_md5: Mapped[str | None] = mapped_column(String(32))
    hash_sha256: Mapped[str | None] = mapped_column(String(64))
    acquisition_date: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    acquisition_tool: Mapped[str | None] = mapped_column(String(100))
    storage_location: Mapped[str | None] = mapped_column(Text)
    nas_path: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    case: Mapped["ForensicsCase"] = relationship("ForensicsCase", back_populates="evidence")
