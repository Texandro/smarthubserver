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

