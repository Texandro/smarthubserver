# -*- coding: utf-8 -*-
"""
SmartHub — Modèles As-Built
Infrastructure + Stack logicielle + Documentation dev
"""
from sqlalchemy import (
    String, Text, Enum, Boolean, Integer, Date,
    ForeignKey, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import DateTime
import uuid
import enum

from ..core.database import Base


# ── Enums Python ──────────────────────────────────────────────

class ServerType(str, enum.Enum):
    cloud_ovh   = "cloud_ovh"
    cloud_other = "cloud_other"
    local_rack  = "local_rack"
    local_tower = "local_tower"

class VpnType(str, enum.Enum):
    site_to_site    = "site_to_site"
    client_to_site  = "client_to_site"
    point_to_point  = "point_to_point"

class VpnProtocol(str, enum.Enum):
    openvpn   = "openvpn"
    wireguard = "wireguard"
    ipsec     = "ipsec"
    other     = "other"

class VpnStatus(str, enum.Enum):
    active   = "active"
    inactive = "inactive"
    planned  = "planned"

class ServiceType(str, enum.Enum):
    system_service = "system_service"
    application    = "application"
    cron_job       = "cron_job"
    script         = "script"

class ScriptLanguage(str, enum.Enum):
    bash       = "bash"
    python     = "python"
    powershell = "powershell"
    other      = "other"

class ScriptTrigger(str, enum.Enum):
    manual   = "manual"
    cron     = "cron"
    on_event = "on_event"
    on_boot  = "on_boot"

class DocLevel(str, enum.Enum):
    opensource = "opensource"
    client     = "client"
    internal   = "internal"

class AsbuiltDocType(str, enum.Enum):
    reseau         = "reseau"
    infrastructure = "infrastructure"
    stack          = "stack"
    dev            = "dev"

class AsbuiltDocStatus(str, enum.Enum):
    draft     = "draft"
    review    = "review"
    validated = "validated"
    archived  = "archived"


# ── Table centrale ────────────────────────────────────────────

class AsbuiltDocument(Base):
    __tablename__ = "asbuilt_documents"

    id           : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id    : Mapped[uuid.UUID]           = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    doc_type     : Mapped[AsbuiltDocType]      = mapped_column(Enum(AsbuiltDocType,    name="asbuilt_doc_type",    create_type=False), nullable=False)
    title        : Mapped[str]                 = mapped_column(String(300), nullable=False)
    version      : Mapped[int]                 = mapped_column(Integer, default=1)
    status       : Mapped[AsbuiltDocStatus]    = mapped_column(Enum(AsbuiltDocStatus,  name="asbuilt_doc_status",  create_type=False), nullable=False, default=AsbuiltDocStatus.draft)
    nas_path     : Mapped[str | None]          = mapped_column(String(500))
    notes        : Mapped[str | None]          = mapped_column(Text)
    generated_at : Mapped[DateTime | None]     = mapped_column(DateTime(timezone=True))
    created_by   : Mapped[uuid.UUID | None]    = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at   : Mapped[DateTime]            = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at   : Mapped[DateTime]            = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    servers     : Mapped[list["InfraServer"]]      = relationship("InfraServer",    back_populates="asbuilt_doc")
    vpn_links   : Mapped[list["InfraVpnLink"]]     = relationship("InfraVpnLink",   back_populates="asbuilt_doc")
    history     : Mapped[list["AsbuiltHistory"]]   = relationship("AsbuiltHistory", back_populates="document", cascade="all, delete-orphan")


# ── Infrastructure : Serveurs ─────────────────────────────────

class InfraServer(Base):
    __tablename__ = "infra_servers"

    id                   : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id            : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id       : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    hostname             : Mapped[str]               = mapped_column(String(200), nullable=False)
    server_type          : Mapped[ServerType]        = mapped_column(Enum(ServerType,  name="server_type",  create_type=False), nullable=False)
    provider             : Mapped[str | None]        = mapped_column(String(100))
    datacenter           : Mapped[str | None]        = mapped_column(String(100))
    reference_provider   : Mapped[str | None]        = mapped_column(String(200))
    ip_public            : Mapped[str | None]        = mapped_column(String(50))
    ip_private           : Mapped[str | None]        = mapped_column(String(50))
    os                   : Mapped[str | None]        = mapped_column(String(200))
    cpu                  : Mapped[str | None]        = mapped_column(String(200))
    ram                  : Mapped[str | None]        = mapped_column(String(100))
    storage              : Mapped[str | None]        = mapped_column(String(200))
    role                 : Mapped[str | None]        = mapped_column(Text)
    date_mise_en_service : Mapped[Date | None]       = mapped_column(Date)
    contract_id          : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"))
    rack_equipment_id    : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="SET NULL"))
    notes                : Mapped[str | None]        = mapped_column(Text)
    created_at           : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at           : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    asbuilt_doc  : Mapped["AsbuiltDocument | None"]         = relationship("AsbuiltDocument", back_populates="servers")
    docker_containers : Mapped[list["StackDockerContainer"]] = relationship("StackDockerContainer", back_populates="server", cascade="all, delete-orphan")
    system_services   : Mapped[list["StackSystemService"]]   = relationship("StackSystemService",   back_populates="server", cascade="all, delete-orphan")
    deployed_scripts  : Mapped[list["StackDeployedScript"]]  = relationship("StackDeployedScript",  back_populates="server", cascade="all, delete-orphan")


# ── Infrastructure : VPN ─────────────────────────────────────

class InfraVpnLink(Base):
    __tablename__ = "infra_vpn_links"

    id             : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id      : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    name           : Mapped[str]               = mapped_column(String(200), nullable=False)
    vpn_type       : Mapped[VpnType]           = mapped_column(Enum(VpnType,       name="vpn_type",     create_type=False), nullable=False)
    protocol       : Mapped[VpnProtocol]       = mapped_column(Enum(VpnProtocol,   name="vpn_protocol", create_type=False), nullable=False)
    endpoint_a     : Mapped[str]               = mapped_column(String(200), nullable=False)
    endpoint_b     : Mapped[str]               = mapped_column(String(200), nullable=False)
    subnet_a       : Mapped[str | None]        = mapped_column(String(100))
    subnet_b       : Mapped[str | None]        = mapped_column(String(100))
    port           : Mapped[int | None]        = mapped_column(Integer)
    encryption     : Mapped[str | None]        = mapped_column(String(100))
    status         : Mapped[VpnStatus]         = mapped_column(Enum(VpnStatus,     name="vpn_status",   create_type=False), nullable=False, default=VpnStatus.active)
    notes          : Mapped[str | None]        = mapped_column(Text)
    created_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    asbuilt_doc : Mapped["AsbuiltDocument | None"] = relationship("AsbuiltDocument", back_populates="vpn_links")


# ── Stack : Docker containers ─────────────────────────────────

class StackDockerContainer(Base):
    __tablename__ = "stack_docker_containers"

    id                  : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id           : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("infra_servers.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id      : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    service_name        : Mapped[str]               = mapped_column(String(200), nullable=False)
    image               : Mapped[str]               = mapped_column(String(300), nullable=False)
    version_tag         : Mapped[str | None]        = mapped_column(String(100))
    ports               : Mapped[dict]              = mapped_column(JSONB, default=list)
    volumes             : Mapped[dict]              = mapped_column(JSONB, default=list)
    env_vars            : Mapped[dict]              = mapped_column(JSONB, default=list)   # secrets masqués
    env_vars_encrypted  : Mapped[str | None]        = mapped_column(Text)                  # secrets chiffrés
    networks            : Mapped[dict]              = mapped_column(JSONB, default=list)
    depends_on          : Mapped[dict]              = mapped_column(JSONB, default=list)
    restart_policy      : Mapped[str | None]        = mapped_column(String(50), default="unless-stopped")
    description         : Mapped[str | None]        = mapped_column(Text)
    url_access          : Mapped[str | None]        = mapped_column(String(500))
    created_at          : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at          : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    server : Mapped["InfraServer"] = relationship("InfraServer", back_populates="docker_containers")


# ── Stack : Services système ──────────────────────────────────

class StackSystemService(Base):
    __tablename__ = "stack_system_services"

    id             : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id      : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("infra_servers.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    name           : Mapped[str]               = mapped_column(String(200), nullable=False)
    service_type   : Mapped[ServiceType]       = mapped_column(Enum(ServiceType,    name="service_type",    create_type=False), nullable=False, default=ServiceType.system_service)
    version        : Mapped[str | None]        = mapped_column(String(100))
    port           : Mapped[int | None]        = mapped_column(Integer)
    config_path    : Mapped[str | None]        = mapped_column(String(500))
    description    : Mapped[str | None]        = mapped_column(Text)
    auto_start     : Mapped[bool]              = mapped_column(Boolean, default=True)
    created_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    server : Mapped["InfraServer"] = relationship("InfraServer", back_populates="system_services")


# ── Stack : Scripts déployés ──────────────────────────────────

class StackDeployedScript(Base):
    __tablename__ = "stack_deployed_scripts"

    id             : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id      : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("infra_servers.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    name           : Mapped[str]               = mapped_column(String(200), nullable=False)
    language       : Mapped[ScriptLanguage]    = mapped_column(Enum(ScriptLanguage, name="script_language", create_type=False), nullable=False, default=ScriptLanguage.bash)
    path           : Mapped[str]               = mapped_column(String(500), nullable=False)
    purpose        : Mapped[str]               = mapped_column(Text, nullable=False)
    trigger        : Mapped[ScriptTrigger]     = mapped_column(Enum(ScriptTrigger,  name="script_trigger",  create_type=False), nullable=False, default=ScriptTrigger.manual)
    cron_schedule  : Mapped[str | None]        = mapped_column(String(100))
    dependencies   : Mapped[str | None]        = mapped_column(Text)
    created_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    server : Mapped["InfraServer"] = relationship("InfraServer", back_populates="deployed_scripts")


# ── Documentation dev ─────────────────────────────────────────

class DevApplication(Base):
    __tablename__ = "dev_applications"

    id             : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id      : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    name           : Mapped[str]               = mapped_column(String(300), nullable=False)
    description    : Mapped[str | None]        = mapped_column(Text)
    repo_url       : Mapped[str | None]        = mapped_column(String(500))
    repo_path      : Mapped[str | None]        = mapped_column(String(500))
    tech_stack     : Mapped[dict]              = mapped_column(JSONB, default=list)
    deployed_on    : Mapped[dict]              = mapped_column(JSONB, default=list)
    created_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at     : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documentation : Mapped[list["DevDocumentation"]] = relationship("DevDocumentation", back_populates="application", cascade="all, delete-orphan")


class DevDocumentation(Base):
    __tablename__ = "dev_documentation"

    id              : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    app_id          : Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), ForeignKey("dev_applications.id", ondelete="CASCADE"), nullable=False)
    asbuilt_doc_id  : Mapped[uuid.UUID | None]   = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="SET NULL"))
    level           : Mapped[DocLevel]           = mapped_column(Enum(DocLevel, name="doc_level", create_type=False), nullable=False)
    content         : Mapped[dict]               = mapped_column(JSONB, default=dict)
    ai_generated    : Mapped[bool]               = mapped_column(Boolean, default=False)
    ai_model        : Mapped[str | None]         = mapped_column(String(100))
    ai_generated_at : Mapped[DateTime | None]    = mapped_column(DateTime(timezone=True))
    validated_by    : Mapped[uuid.UUID | None]   = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    validated_at    : Mapped[DateTime | None]    = mapped_column(DateTime(timezone=True))
    nas_path        : Mapped[str | None]         = mapped_column(String(500))
    version         : Mapped[int]                = mapped_column(Integer, default=1)
    created_at      : Mapped[DateTime]           = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at      : Mapped[DateTime]           = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    application : Mapped["DevApplication"] = relationship("DevApplication", back_populates="documentation")


# ── Historique versions ───────────────────────────────────────

class AsbuiltHistory(Base):
    __tablename__ = "asbuilt_history"

    id              : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id     : Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), ForeignKey("asbuilt_documents.id", ondelete="CASCADE"), nullable=False)
    version         : Mapped[int]               = mapped_column(Integer, nullable=False)
    nas_path        : Mapped[str | None]        = mapped_column(String(500))
    changed_by      : Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    change_summary  : Mapped[str | None]        = mapped_column(Text)
    created_at      : Mapped[DateTime]          = mapped_column(DateTime(timezone=True), server_default=func.now())

    document : Mapped["AsbuiltDocument"] = relationship("AsbuiltDocument", back_populates="history")
