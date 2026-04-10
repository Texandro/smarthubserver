from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import Optional
from datetime import date

from ..core.database import get_db
from ..models.project import Project, KanbanColumn, ProjectStatus
from ..models.auth import User
from ..auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


def _project_dict(p: Project, client_name: str = "", column_name: str = "") -> dict:
    dw = None
    if p.waiting_since and p.status == ProjectStatus.waiting_third_party:
        dw = (date.today() - p.waiting_since).days
    return {
        "id":               str(p.id),
        "client_id":        str(p.client_id) if p.client_id else None,
        "client_name":      client_name,
        "contract_id":      str(p.contract_id) if p.contract_id else None,
        "title":            p.title,
        "description":      p.description,
        "status":           p.status,
        "priority":         p.priority,
        "kanban_column_id": str(p.kanban_column_id) if p.kanban_column_id else None,
        "kanban_column":    column_name,
        "waiting_for":      p.waiting_for,
        "waiting_since":    p.waiting_since.isoformat() if p.waiting_since else None,
        "days_waiting":     dw,
        "auto_remind_days": p.auto_remind_days,
        "needs_reminder":   dw is not None and dw >= p.auto_remind_days,
        "due_date":         p.due_date.isoformat() if p.due_date else None,
        "estimated_hours":  float(p.estimated_hours) if p.estimated_hours else None,
        "tags":             p.tags,
        "created_at":       p.created_at.isoformat(),
        "updated_at":       p.updated_at.isoformat(),
    }


@router.get("/kanban", response_model=list[dict])
async def get_kanban(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    cols = await db.execute(select(KanbanColumn).order_by(KanbanColumn.position))
    result = []
    for col in cols.scalars().all():
        projs = await db.execute(
            select(Project)
            .where(Project.kanban_column_id == col.id, Project.status != ProjectStatus.archived)
            .order_by(Project.priority.desc(), Project.updated_at.desc())
        )
        result.append({
            "id":                 str(col.id),
            "name":               col.name,
            "color":              col.color,
            "position":           col.position,
            "auto_escalate_days": col.auto_escalate_days,
            "projects":           [_project_dict(p, column_name=col.name) for p in projs.scalars().all()],
        })
    return result


@router.get("/", response_model=list[dict])
async def list_projects(
    client_id : Optional[UUID] = None,
    status    : Optional[str]  = None,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(get_current_user),
):
    query = select(Project).where(Project.status != ProjectStatus.archived)
    if client_id:
        query = query.where(Project.client_id == client_id)
    if status:
        query = query.where(Project.status == status)
    query = query.order_by(Project.updated_at.desc())
    result = await db.execute(query)
    return [_project_dict(p) for p in result.scalars().all()]


@router.get("/waiting", response_model=list[dict])
async def get_waiting(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT id, title, status, priority, waiting_for, waiting_since,
               auto_remind_days, days_waiting, needs_reminder,
               client_name, kanban_column
        FROM v_projects_waiting ORDER BY days_waiting DESC
    """))
    return [dict(r) for r in result.mappings().all()]


@router.get("/{project_id}", response_model=dict)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return _project_dict(project)


@router.post("/", response_model=dict, status_code=201)
async def create_project(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    for field in ["id", "created_at", "updated_at", "client_name", "kanban_column", "days_waiting", "needs_reminder"]:
        data.pop(field, None)

    if not data.get("kanban_column_id"):
        col = await db.execute(select(KanbanColumn).order_by(KanbanColumn.position).limit(1))
        first = col.scalar_one_or_none()
        if first:
            data["kanban_column_id"] = str(first.id)

    project = Project(**data)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return _project_dict(project)


@router.patch("/{project_id}", response_model=dict)
async def update_project(
    project_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    for field in ["id", "created_at", "updated_at", "client_name", "kanban_column", "days_waiting", "needs_reminder"]:
        data.pop(field, None)
    for key, value in data.items():
        if hasattr(project, key):
            setattr(project, key, value)
    await db.flush()
    await db.refresh(project)
    return _project_dict(project)


@router.patch("/{project_id}/move", response_model=dict)
async def move_project(
    project_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    if "kanban_column_id" in data:
        project.kanban_column_id = data["kanban_column_id"]
    if "status" in data:
        project.status = data["status"]
    await db.flush()
    await db.refresh(project)
    return _project_dict(project)
