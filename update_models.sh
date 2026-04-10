#!/bin/bash
set -e
echo '🔧 Mise à jour des modèles SQLAlchemy...'

cat > /srv/smarthub/api/app/models/client.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, Numeric, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
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
    status: Mapped[ClientStatus] = mapped_column(Enum(ClientStatus, name="client_status", create_type=False), nullable=False, default=ClientStatus.actif)
    client_type: Mapped[ClientType] = mapped_column(Enum(ClientType, name="client_type", create_type=False), nullable=False, default=ClientType.entreprise)
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
    projects: Mapped[list["Project"]] = relationship("Project", back_populates="client")
    equipment: Mapped[list["Equipment"]] = relationship("Equipment", back_populates="client")
    forensics_cases: Mapped[list["ForensicsCase"]] = relationship("ForensicsCase", back_populates="client")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    nas_path: Mapped[str | None] = mapped_column(String(500))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="sites")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"))
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[str | None] = mapped_column(String(100))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="contacts")

HEREDOC

cat > /srv/smarthub/api/app/models/contract.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, Numeric, Boolean, Date, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base
import enum


class ContractType(str, enum.Enum):
    maintenance = "maintenance"
    lm_forensics = "lm_forensics"
    lm_datashredding = "lm_datashredding"
    lm_dev = "lm_dev"
    lm_it_management = "lm_it_management"
    devis = "devis"
    autre = "autre"


class ContractStatus(str, enum.Enum):
    brouillon = "brouillon"
    envoyé = "envoyé"
    signé = "signé"
    actif = "actif"
    expiré = "expiré"
    résilié = "résilié"


class BillingType(str, enum.Enum):
    forfait_mensuel = "forfait_mensuel"
    forfait_projet = "forfait_projet"
    regie = "regie"
    inclus = "inclus"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"))
    contract_type: Mapped[ContractType] = mapped_column(Enum(ContractType, name="contract_type", create_type=False), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus, name="contract_status", create_type=False), nullable=False, default=ContractStatus.brouillon)
    start_date: Mapped[Date | None] = mapped_column(Date)
    end_date: Mapped[Date | None] = mapped_column(Date)
    renewal_reminder_days: Mapped[int] = mapped_column(Integer, default=30)
    billing_type: Mapped[BillingType] = mapped_column(Enum(BillingType, name="billing_type", create_type=False), nullable=False)
    sold_hours: Mapped[float | None] = mapped_column(Numeric(8, 2))
    sold_budget: Mapped[float | None] = mapped_column(Numeric(10, 2))
    hourly_rate: Mapped[float | None] = mapped_column(Numeric(8, 2))
    monthly_amount: Mapped[float | None] = mapped_column(Numeric(10, 2))
    falco_project_id: Mapped[str | None] = mapped_column(String(100))
    docuseal_document_id: Mapped[str | None] = mapped_column(String(100))
    signed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    signed_by_name: Mapped[str | None] = mapped_column(String(200))
    signed_by_email: Mapped[str | None] = mapped_column(String(200))
    signed_pdf_path: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    template_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relations
    client: Mapped["Client"] = relationship("Client", back_populates="contracts")
    items: Mapped[list["ContractItem"]] = relationship("ContractItem", back_populates="contract", cascade="all, delete-orphan")
    time_sessions: Mapped[list["TimeSession"]] = relationship("TimeSession", back_populates="contract")


class ContractItem(Base):
    __tablename__ = "contract_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    quantity: Mapped[float] = mapped_column(Numeric(8, 2), default=1)
    unit: Mapped[str | None] = mapped_column(String(50))
    is_included: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)

    contract: Mapped["Contract"] = relationship("Contract", back_populates="items")

HEREDOC

cat > /srv/smarthub/api/app/models/project.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, Boolean, Date, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
from ..core.database import Base
import enum


class ProjectStatus(str, enum.Enum):
    open = "open"
    waiting_third_party = "waiting_third_party"
    to_invoice = "to_invoice"
    done = "done"
    archived = "archived"


class ProjectPriority(str, enum.Enum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class KanbanColumn(Base):
    __tablename__ = "kanban_columns"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#607D8B")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_escalate_days: Mapped[int | None] = mapped_column(Integer)

    projects: Mapped[list["Project"]] = relationship("Project", back_populates="kanban_column")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id", ondelete="SET NULL"))
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(Enum(ProjectStatus, name="project_status", create_type=False), nullable=False, default=ProjectStatus.open)
    priority: Mapped[ProjectPriority] = mapped_column(Enum(ProjectPriority, name="project_priority", create_type=False), nullable=False, default=ProjectPriority.normal)
    kanban_column_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kanban_columns.id", ondelete="SET NULL"))
    waiting_for: Mapped[str | None] = mapped_column(String(200))
    waiting_since: Mapped[Date | None] = mapped_column(Date)
    auto_remind_days: Mapped[int] = mapped_column(Integer, default=5)
    last_reminded_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True))
    due_date: Mapped[Date | None] = mapped_column(Date)
    estimated_hours: Mapped[float | None] = mapped_column()
    tags: Mapped[list[str] | None] = mapped_column()
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="projects")
    kanban_column: Mapped["KanbanColumn"] = relationship("KanbanColumn", back_populates="projects")
    time_sessions: Mapped[list["TimeSession"]] = relationship("TimeSession", back_populates="project")

HEREDOC

cat > /srv/smarthub/api/app/models/equipment.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, Boolean, Date, DateTime, ForeignKey
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
    billed_amount: Mapped[float | None] = mapped_column()
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="interventions")

HEREDOC

cat > /srv/smarthub/api/app/models/forensics.py << 'HEREDOC'
from sqlalchemy import String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
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
    status: Mapped[ForensicsStatus] = mapped_column(Enum(ForensicsStatus, name="forensics_status", create_type=False), nullable=False, default=ForensicsStatus.ouvert)
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

HEREDOC

cat > /srv/smarthub/api/app/models/timetrack.py << 'HEREDOC'
from sqlalchemy import String, Text, Boolean, Numeric, DateTime, ForeignKey
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
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_included_in_contract: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hourly_rate_applied: Mapped[float | None] = mapped_column(Numeric(8, 2))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="time_sessions")
    contract: Mapped["Contract"] = relationship("Contract", back_populates="time_sessions")
    project: Mapped["Project"] = relationship("Project", back_populates="time_sessions")
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

    session: Mapped["TimeSession"] = relationship("TimeSession", back_populates="report")

HEREDOC

cat > /srv/smarthub/api/app/models/__init__.py << 'HEREDOC'
from .client import Client, Site, Contact
from .contract import Contract, ContractItem
from .project import KanbanColumn, Project
from .equipment import Equipment, WorkshopIntervention
from .forensics import ForensicsCase, ForensicsEvidence
from .timetrack import TimeSession, SessionReport

__all__ = [
    "Client", "Site", "Contact",
    "Contract", "ContractItem",
    "KanbanColumn", "Project",
    "Equipment", "WorkshopIntervention",
    "ForensicsCase", "ForensicsEvidence",
    "TimeSession", "SessionReport",
]

HEREDOC

echo '✅ Modèles mis à jour!'
echo '🔄 Redémarrage API...'
cd /srv/smarthub && docker compose restart api
sleep 3
docker logs smarthub-api --tail=5
