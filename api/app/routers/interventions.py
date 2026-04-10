"""
SmartHub — Router Interventions On-Site
GET  /api/v1/interventions/          → liste (filtrable client/status)
POST /api/v1/interventions/          → créer
GET  /api/v1/interventions/{id}      → détail
PATCH /api/v1/interventions/{id}     → modifier
POST /api/v1/interventions/{id}/start  → démarrer
POST /api/v1/interventions/{id}/stop   → terminer + rapport
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from ..core.database import get_db
from ..models.intervention import OnSiteIntervention, OnsiteStatus
from ..models.client import Client
from ..auth import get_current_user, require_owner
from ..models.auth import User

router = APIRouter(prefix="/interventions", tags=["interventions"])


def _to_dict(i: OnSiteIntervention, client_name: str = "") -> dict:
    return {
        "id"              : str(i.id),
        "client_id"       : str(i.client_id),
        "client_name"     : client_name or "",
        "site_id"         : str(i.site_id) if i.site_id else None,
        "contract_id"     : str(i.contract_id) if i.contract_id else None,
        "session_id"      : str(i.session_id) if i.session_id else None,
        "titre"           : i.titre,
        "description"     : i.description,
        "status"          : i.status,
        "planned_at"      : i.planned_at.isoformat() if i.planned_at else None,
        "started_at"      : i.started_at.isoformat() if i.started_at else None,
        "ended_at"        : i.ended_at.isoformat() if i.ended_at else None,
        "technicien"      : i.technicien,
        "notes_depart"    : i.notes_depart,
        "notes_fin"       : i.notes_fin,
        "materiel_utilise": i.materiel_utilise,
        "is_billable"     : i.is_billable,
        "pdf_report_path" : i.pdf_report_path,
        "created_at"      : i.created_at.isoformat(),
        "updated_at"      : i.updated_at.isoformat(),
    }


@router.get("/", response_model=list[dict])
async def list_interventions(
    client_id : Optional[UUID] = None,
    status    : Optional[str]  = None,
    limit     : int            = 100,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(get_current_user),
):
    query = (
        select(OnSiteIntervention, Client.name.label("client_name"))
        .join(Client, OnSiteIntervention.client_id == Client.id)
        .order_by(OnSiteIntervention.created_at.desc())
        .limit(limit)
    )
    if client_id:
        query = query.where(OnSiteIntervention.client_id == client_id)
    if status:
        query = query.where(OnSiteIntervention.status == status)

    result = await db.execute(query)
    return [_to_dict(i, cn) for i, cn in result.all()]


@router.get("/{intervention_id}", response_model=dict)
async def get_intervention(
    intervention_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OnSiteIntervention, Client.name.label("client_name"))
        .join(Client, OnSiteIntervention.client_id == Client.id)
        .where(OnSiteIntervention.id == intervention_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Intervention introuvable")
    return _to_dict(row[0], row[1])


@router.post("/", response_model=dict, status_code=201)
async def create_intervention(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Forcer le technicien = nom de l'utilisateur courant
    data.setdefault("technicien", current_user.name)

    # Nettoyer tous les champs non présents dans le modèle
    for f in ["elapsed_min", "client_name", "lieu", "budget_min",
              "contract_ref", "id", "updated_at", "created_at"]:
        data.pop(f, None)

    # Convertir les champs datetime string → datetime object
    from datetime import datetime
    import uuid as _uuid
    for dt_field in ["started_at", "ended_at", "planned_at"]:
        val = data.get(dt_field)
        if isinstance(val, str) and val:
            try:
                data[dt_field] = datetime.fromisoformat(val)
            except ValueError:
                data.pop(dt_field, None)

    # Convertir les champs UUID string → uuid.UUID object
    for uuid_field in ["client_id", "contract_id", "site_id", "session_id"]:
        val = data.get(uuid_field)
        if isinstance(val, str) and val:
            try:
                data[uuid_field] = _uuid.UUID(val)
            except ValueError:
                data.pop(uuid_field, None)
        elif val == "" or val is None:
            data.pop(uuid_field, None)

    interv = OnSiteIntervention(**data)
    db.add(interv)
    await db.flush()
    await db.refresh(interv)

    client = await db.execute(select(Client).where(Client.id == interv.client_id))
    c = client.scalar_one_or_none()
    return _to_dict(interv, c.name if c else "")


@router.patch("/{intervention_id}", response_model=dict)
async def update_intervention(
    intervention_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(OnSiteIntervention).where(OnSiteIntervention.id == intervention_id)
    )
    interv = result.scalar_one_or_none()
    if not interv:
        raise HTTPException(status_code=404, detail="Intervention introuvable")

    # Exclure les champs GENERATED
    for key in ["elapsed_min", "client_name"]:
        data.pop(key, None)

    for key, value in data.items():
        if hasattr(interv, key):
            setattr(interv, key, value)

    await db.flush()
    await db.refresh(interv)

    client = await db.execute(select(Client).where(Client.id == interv.client_id))
    c = client.scalar_one_or_none()
    return _to_dict(interv, c.name if c else "")


@router.post("/{intervention_id}/start", response_model=dict)
async def start_intervention(
    intervention_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Démarre une intervention — enregistre le started_at."""
    result = await db.execute(
        select(OnSiteIntervention).where(OnSiteIntervention.id == intervention_id)
    )
    interv = result.scalar_one_or_none()
    if not interv:
        raise HTTPException(status_code=404, detail="Intervention introuvable")
    if interv.started_at:
        raise HTTPException(status_code=400, detail="Intervention déjà démarrée")

    interv.started_at = datetime.now(timezone.utc)
    interv.status     = OnsiteStatus.en_cours
    await db.flush()
    await db.refresh(interv)

    client = await db.execute(select(Client).where(Client.id == interv.client_id))
    c = client.scalar_one_or_none()
    return _to_dict(interv, c.name if c else "")


@router.post("/{intervention_id}/stop", response_model=dict)
async def stop_intervention(
    intervention_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Termine une intervention.
    Body: {"notes_fin": "...", "materiel_utilise": "..."}
    """
    result = await db.execute(
        select(OnSiteIntervention).where(OnSiteIntervention.id == intervention_id)
    )
    interv = result.scalar_one_or_none()
    if not interv:
        raise HTTPException(status_code=404, detail="Intervention introuvable")

    interv.ended_at         = datetime.now(timezone.utc)
    interv.status           = OnsiteStatus.terminee
    interv.notes_fin        = data.get("notes_fin", interv.notes_fin)
    interv.materiel_utilise = data.get("materiel_utilise", interv.materiel_utilise)

    await db.flush()
    await db.refresh(interv)

    client = await db.execute(select(Client).where(Client.id == interv.client_id))
    c = client.scalar_one_or_none()
    return _to_dict(interv, c.name if c else "")
