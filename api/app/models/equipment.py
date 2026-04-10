from sqlalchemy import String, Text, Enum, Boolean, Date, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base
import enum


class EquipmentType(str, enum.Enum):
    desktop = "desktop"
    laptop = "laptop"
    server = "server"
    nas = "nas"
    switch = "switch"
    router = "router"
    printer = "printer"
    other = "other"


class EquipmentStatus(str, enum.Enum):
    active = "active"
    in_repair = "in_repair"
    retired = "retired"
    shredded = "shredded"


class InterventionType(str, enum.Enum):
    maintenance = "maintenance"
    repair = "repair"
    datashredding = "datashredding"
    forensics_prep = "forensics_prep"
    other = "other"


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"))
    serial_number: Mapped[str | None] = mapped_column(String(200), unique=True)
    asset_tag: Mapped[str | None] = mapped_column(String(100))
    type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType, name="equipment_type", create_type=False), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    specs_json: Mapped[dict | None] = mapped_column(JSONB)
    purchase_date: Mapped[Date | None] = mapped_column(Date)
    warranty_until: Mapped[Date | None] = mapped_column(Date)
    status: Mapped[EquipmentStatus] = mapped_column(Enum(EquipmentStatus, name="equipment_status", create_type=False), nullable=False, default=EquipmentStatus.active)
    nas_path: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="equipment")
    interventions: Mapped[list["WorkshopIntervention"]] = relationship("WorkshopIntervention", back_populates="equipment")


class WorkshopIntervention(Base):
    __tablename__ = "workshop_interventions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    equipment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("equipment.id"), nullable=False)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("time_sessions.id", ondelete="SET NULL"))
    intervention_type: Mapped[InterventionType] = mapped_column(Enum(InterventionType, name="intervention_type", create_type=False), nullable=False)
    intervention_date: Mapped[Date] = mapped_column(Date, nullable=False)
    technician: Mapped[str] = mapped_column(String(100), default="Mathieu Pleitinx")
    summary: Mapped[str | None] = mapped_column(Text)
    checks_json: Mapped[dict | None] = mapped_column(JSONB)
    hdshredder_report_path: Mapped[str | None] = mapped_column(String(500))
    pdf_report_path: Mapped[str | None] = mapped_column(String(500))
    pdf_generated_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    is_billable: Mapped[bool] = mapped_column(Boolean, default=True)
    billed_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="interventions")
