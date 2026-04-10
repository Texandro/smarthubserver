# -*- coding: utf-8 -*-
"""
SmartHub — Modèles As-Built Réseau
Catalogue + Rack + Patch Panel + Floor Plan
"""
from sqlalchemy import String, Text, Enum, Boolean, Integer, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
import uuid, enum
from ..core.database import Base


class EquipmentCategory(str, enum.Enum):
    switch       = "switch"
    router       = "router"
    access_point = "access_point"
    patch_panel  = "patch_panel"
    server       = "server"
    nas          = "nas"
    ups          = "ups"
    pdu          = "pdu"
    shelf        = "shelf"
    other        = "other"

class CableType(str, enum.Enum):
    cat5e      = "cat5e"
    cat6       = "cat6"
    cat6a      = "cat6a"
    fiber_om3  = "fiber_om3"
    fiber_om4  = "fiber_om4"
    fiber_os2  = "fiber_os2"

class PortStatus(str, enum.Enum):
    active       = "active"
    reserved     = "reserved"
    disconnected = "disconnected"

class RackDocType(str, enum.Enum):
    full_cabinet   = "full_cabinet"
    rack_only      = "rack_only"
    floorplan_only = "floorplan_only"

class RackDocStatus(str, enum.Enum):
    draft     = "draft"
    published = "published"


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    id            : Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manufacturer  : Mapped[str]                    = mapped_column(String(100), nullable=False)
    model         : Mapped[str]                    = mapped_column(String(200), nullable=False)
    category      : Mapped[EquipmentCategory]      = mapped_column(Enum(EquipmentCategory, name="equipment_category", create_type=False), nullable=False)
    height_u      : Mapped[int]                    = mapped_column(Integer, default=1)
    is_rackmount  : Mapped[bool]                   = mapped_column(Boolean, default=True)
    port_count    : Mapped[int | None]             = mapped_column(Integer)
    poe           : Mapped[bool]                   = mapped_column(Boolean, default=False)
    poe_budget_w  : Mapped[int | None]             = mapped_column(Integer)
    max_power_w   : Mapped[int | None]             = mapped_column(Integer)
    notes         : Mapped[str | None]             = mapped_column(Text)
    is_custom     : Mapped[bool]                   = mapped_column(Boolean, default=False)
    created_by    : Mapped[uuid.UUID | None]       = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at    : Mapped[DateTime]               = mapped_column(DateTime(timezone=True), server_default=func.now())


class RackDocument(Base):
    __tablename__ = "rack_documents"
    id          : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id   : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title       : Mapped[str]              = mapped_column(String(300), nullable=False)
    doc_type    : Mapped[RackDocType]      = mapped_column(Enum(RackDocType,   name="rack_doc_type",   create_type=False), default=RackDocType.full_cabinet)
    status      : Mapped[RackDocStatus]    = mapped_column(Enum(RackDocStatus, name="rack_doc_status", create_type=False), default=RackDocStatus.draft)
    version     : Mapped[int]              = mapped_column(Integer, default=1)
    notes       : Mapped[str | None]       = mapped_column(Text)
    nas_path    : Mapped[str | None]       = mapped_column(String(500))
    created_by  : Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at  : Mapped[DateTime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at  : Mapped[DateTime]         = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rack_configs : Mapped[list["RackConfig"]]          = relationship("RackConfig",         back_populates="document", cascade="all, delete-orphan")
    floor_plans  : Mapped[list["FloorPlan"]]           = relationship("FloorPlan",          back_populates="document", cascade="all, delete-orphan")
    versions     : Mapped[list["RackDocumentVersion"]] = relationship("RackDocumentVersion",back_populates="document", cascade="all, delete-orphan")


class RackDocumentVersion(Base):
    __tablename__ = "rack_document_versions"
    id          : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id : Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), ForeignKey("rack_documents.id", ondelete="CASCADE"), nullable=False)
    version     : Mapped[int]              = mapped_column(Integer, nullable=False)
    nas_path    : Mapped[str | None]       = mapped_column(String(500))
    version_note: Mapped[str | None]       = mapped_column(Text)
    created_by  : Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at  : Mapped[DateTime]         = mapped_column(DateTime(timezone=True), server_default=func.now())
    document    : Mapped["RackDocument"]   = relationship("RackDocument", back_populates="versions")


class RackConfig(Base):
    __tablename__ = "rack_configs"
    id          : Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id : Mapped[uuid.UUID]  = mapped_column(UUID(as_uuid=True), ForeignKey("rack_documents.id", ondelete="CASCADE"), nullable=False)
    rack_size_u : Mapped[int]        = mapped_column(Integer, default=12)
    rack_label  : Mapped[str]        = mapped_column(String(200), default="Rack A")
    location    : Mapped[str | None] = mapped_column(String(300))
    created_at  : Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at  : Mapped[DateTime]   = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document    : Mapped["RackDocument"]           = relationship("RackDocument", back_populates="rack_configs")
    slots       : Mapped[list["RackEquipmentSlot"]]= relationship("RackEquipmentSlot", back_populates="rack", cascade="all, delete-orphan")


class RackEquipmentSlot(Base):
    __tablename__ = "rack_equipment_slots"
    id                  : Mapped[uuid.UUID]                = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rack_id             : Mapped[uuid.UUID]                = mapped_column(UUID(as_uuid=True), ForeignKey("rack_configs.id", ondelete="CASCADE"), nullable=False)
    catalog_item_id     : Mapped[uuid.UUID | None]         = mapped_column(UUID(as_uuid=True), ForeignKey("catalog_items.id", ondelete="SET NULL"))
    position_u          : Mapped[int]                      = mapped_column(Integer, nullable=False)
    height_u            : Mapped[int]                      = mapped_column(Integer, default=1)
    hostname            : Mapped[str | None]               = mapped_column(String(200))
    ip_address          : Mapped[str | None]               = mapped_column(String(50))
    mac_address         : Mapped[str | None]               = mapped_column(String(50))
    serial_number       : Mapped[str | None]               = mapped_column(String(200))
    role                : Mapped[str | None]               = mapped_column(Text)
    custom_manufacturer : Mapped[str | None]               = mapped_column(String(100))
    custom_model        : Mapped[str | None]               = mapped_column(String(200))
    custom_category     : Mapped[EquipmentCategory | None] = mapped_column(Enum(EquipmentCategory, name="equipment_category", create_type=False))
    created_at          : Mapped[DateTime]                 = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at          : Mapped[DateTime]                 = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    rack         : Mapped["RackConfig"]                   = relationship("RackConfig", back_populates="slots")
    catalog_item : Mapped["CatalogItem | None"]           = relationship("CatalogItem")
    patch_ports  : Mapped[list["PatchPanelMapping"]]      = relationship("PatchPanelMapping", back_populates="slot", cascade="all, delete-orphan")


class PatchPanelMapping(Base):
    __tablename__ = "patch_panel_mappings"
    id                    : Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slot_id               : Mapped[uuid.UUID]    = mapped_column(UUID(as_uuid=True), ForeignKey("rack_equipment_slots.id", ondelete="CASCADE"), nullable=False)
    port_number           : Mapped[int]          = mapped_column(Integer, nullable=False)
    destination_label     : Mapped[str | None]   = mapped_column(String(300))
    cable_type            : Mapped[CableType]    = mapped_column(Enum(CableType,   name="cable_type",   create_type=False), default=CableType.cat6)
    cable_length_m        : Mapped[float | None] = mapped_column(Numeric(6,1))
    connected_switch_port : Mapped[str | None]   = mapped_column(String(200))
    status                : Mapped[PortStatus]   = mapped_column(Enum(PortStatus,  name="port_status",  create_type=False), default=PortStatus.disconnected)
    notes                 : Mapped[str | None]   = mapped_column(Text)
    created_at            : Mapped[DateTime]     = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at            : Mapped[DateTime]     = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    slot : Mapped["RackEquipmentSlot"] = relationship("RackEquipmentSlot", back_populates="patch_ports")


class FloorPlan(Base):
    __tablename__ = "floor_plans"
    id            : Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id   : Mapped[uuid.UUID]   = mapped_column(UUID(as_uuid=True), ForeignKey("rack_documents.id", ondelete="CASCADE"), nullable=False)
    rooms         : Mapped[dict]        = mapped_column(JSONB, default=list)
    outlets       : Mapped[dict]        = mapped_column(JSONB, default=list)
    devices       : Mapped[dict]        = mapped_column(JSONB, default=list)
    rack_position : Mapped[dict | None] = mapped_column(JSONB)
    canvas_width  : Mapped[int]         = mapped_column(Integer, default=800)
    canvas_height : Mapped[int]         = mapped_column(Integer, default=600)
    created_at    : Mapped[DateTime]    = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at    : Mapped[DateTime]    = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    document : Mapped["RackDocument"] = relationship("RackDocument", back_populates="floor_plans")
