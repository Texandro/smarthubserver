"""
SmartHub — Modèle Planning
Créneaux prévisionnels + règles de récurrence.
"""
import uuid
from sqlalchemy import String, Text, Integer, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from ..core.database import Base


class RecurrenceRule(Base):
    __tablename__ = "recurrence_rules"

    id         : Mapped[int]            = mapped_column(Integer, primary_key=True, autoincrement=True)
    rrule      : Mapped[str]            = mapped_column(String(255), nullable=False)
    until_date : Mapped["Date | None"]  = mapped_column(Date)
    exceptions : Mapped[list]           = mapped_column(JSONB, nullable=False, default=list)
    created_at : Mapped[DateTime]       = mapped_column(DateTime(timezone=True), server_default=func.now())

    slots: Mapped[list["PlanningSlot"]] = relationship("PlanningSlot", back_populates="recurrence_rule")


class PlanningSlot(Base):
    __tablename__ = "planning_slots"

    id           : Mapped[uuid.UUID]              = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title        : Mapped[str]                    = mapped_column(String(255), nullable=False)

    client_id    : Mapped[uuid.UUID | None]       = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id",  ondelete="SET NULL"))
    dossier_id   : Mapped[uuid.UUID | None]       = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))

    context_type : Mapped[str]                    = mapped_column(String(32), nullable=False, default="manuel")
    context_id   : Mapped[uuid.UUID | None]       = mapped_column(UUID(as_uuid=True))
    context_ref  : Mapped[str | None]             = mapped_column(String(255))

    start_at     : Mapped[DateTime]               = mapped_column(DateTime(timezone=True), nullable=False)
    duration_min : Mapped[int]                    = mapped_column(Integer, nullable=False)

    # planned | in_progress | done | missed | overrun (ENUM côté Postgres)
    status       : Mapped[str]                    = mapped_column(String(16), nullable=False, default="planned")
    notes        : Mapped[str | None]             = mapped_column(Text)

    recurrence_rule_id   : Mapped[int | None]      = mapped_column(Integer, ForeignKey("recurrence_rules.id", ondelete="SET NULL"))
    recurrence_parent_id : Mapped[uuid.UUID | None]= mapped_column(UUID(as_uuid=True), ForeignKey("planning_slots.id", ondelete="CASCADE"))

    actual_session_id    : Mapped[uuid.UUID | None]= mapped_column(UUID(as_uuid=True), ForeignKey("time_sessions.id", ondelete="SET NULL"))
    actual_duration_min  : Mapped[int | None]      = mapped_column(Integer)

    created_at : Mapped[DateTime]                 = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at : Mapped[DateTime]                 = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by : Mapped[uuid.UUID | None]         = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))

    recurrence_rule: Mapped["RecurrenceRule | None"] = relationship("RecurrenceRule", back_populates="slots")

    __table_args__ = (
        CheckConstraint("duration_min > 0", name="planning_slots_duration_positive"),
    )
