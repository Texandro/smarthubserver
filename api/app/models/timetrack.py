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

    # duration_minutes et amount sont GENERATED ALWAYS AS côté PostgreSQL
    # → pas déclarées dans le modèle, lues via getattr(..., None) dans les routers

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
