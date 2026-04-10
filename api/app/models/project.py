from sqlalchemy import String, Text, Enum, Boolean, Date, DateTime, Integer, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID, ARRAY
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
    estimated_hours: Mapped[float | None] = mapped_column(Numeric(6, 2))
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    client: Mapped["Client"] = relationship("Client", back_populates="projects")
    kanban_column: Mapped["KanbanColumn"] = relationship("KanbanColumn", back_populates="projects")
    time_sessions: Mapped[list["TimeSession"]] = relationship("TimeSession", back_populates="project")
