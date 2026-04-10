from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import Optional
from datetime import date

from ..core.database import get_db
from ..models.equipment import Equipment, WorkshopIntervention, EquipmentStatus
from ..models.client import Client
from ..models.auth import User
from ..auth import get_current_user

router = APIRouter(prefix="/equipment", tags=["equipment"])
# Alias /atelier/ → même router
atelier_router = APIRouter(prefix="/atelier", tags=["atelier"])


def _eq_dict(e: Equipment, client_name: str = "") -> dict:
    return {
        "id":             str(e.id),
        "client_id":      str(e.client_id),
        "client_name":    client_name,
        "site_id":        str(e.site_id) if e.site_id else None,
        "serial_number":  e.serial_number,
        "asset_tag":      e.asset_tag,
        "type":           e.type,
        "brand":          e.brand,
        "model":          e.model,
        "specs_json":     e.specs_json,
        "purchase_date":  e.purchase_date.isoformat() if e.purchase_date else None,
        "warranty_until": e.warranty_until.isoformat() if e.warranty_until else None,
        "status":         e.status,
        "nas_path":       e.nas_path,
        "notes":          e.notes,
        "created_at":     e.created_at.isoformat(),
    }


def _intervention_dict(i: WorkshopIntervention) -> dict:
    return {
        "id":                   str(i.id),
        "equipment_id":         str(i.equipment_id),
        "contract_id":          str(i.contract_id) if i.contract_id else None,
        "session_id":           str(i.session_id) if i.session_id else None,
        "intervention_type":    i.intervention_type,
        "intervention_date":    i.intervention_date.isoformat(),
        "technician":           i.technician,
        "summary":              i.summary,
        "checks_json":          i.checks_json,
        "hdshredder_report_path": i.hdshredder_report_path,
        "pdf_report_path":      i.pdf_report_path,
        "is_billable":          i.is_billable,
        "created_at":           i.created_at.isoformat(),
        # Alias pour le module Atelier du Qt
        "reference":            f"WI-{str(i.id)[:8].upper()}",
        "probleme":             i.summary,
        "heures_prestees":      None,  # non stocké en BDD atelier
    }



INTERV_TYPE_MAP = {
    "diagnostic":    "repair",
    "cleaning":      "maintenance",
    "data_recovery": "repair",
    "data_shredding":"datashredding",
    "installation":  "maintenance",
    "upgrade":       "maintenance",
    "repair":        "repair",
    "other":         "other",
    "forensics_prep":"forensics_prep",
}

def _atelier_combined(eq: Equipment, interv: WorkshopIntervention, client_name: str = "") -> dict:
    """Retourne un dict plat équipement+intervention pour le Qt Atelier."""
    extra = interv.checks_json or {}
    return {
        "id":               str(interv.id),
        "equipment_id":     str(eq.id),
        "client_id":        str(eq.client_id),
        "client_name":      client_name,
        "brand":            eq.brand or "",
        "model":            eq.model or "",
        "serial_number":    eq.serial_number,
        "device_type":      str(eq.type) if eq.type else "",
        "intervention_type": str(interv.intervention_type) if interv.intervention_type else "",
        "intervention_date": interv.intervention_date.isoformat() if interv.intervention_date else "",
        "status":           extra.get("qt_status", "diagnostic"),
        "description":      interv.summary or "",
        "work_done":        extra.get("work_done"),
        "labor_hours":      extra.get("labor_hours"),
        "parts_cost":       extra.get("parts_cost"),
        "notes":            extra.get("notes"),
        "technician":       interv.technician or "",
    }

# ── Equipment ──────────────────────────────────────────────

@router.get("/", response_model=list[dict])
async def list_equipment(
    client_id : Optional[UUID] = None,
    status    : Optional[str]  = None,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(get_current_user),
):
    query = select(Equipment).order_by(Equipment.created_at.desc())
    if client_id:
        query = query.where(Equipment.client_id == client_id)
    if status:
        query = query.where(Equipment.status == status)
    result = await db.execute(query)
    items = result.scalars().all()
    out = []
    for e in items:
        cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(e.client_id)})
        out.append(_eq_dict(e, cr.scalar_one_or_none() or ""))
    return out


@atelier_router.get("/", response_model=list[dict])
async def list_atelier_fiches(
    client_id : Optional[UUID] = None,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(get_current_user),
):
    """Retourne les fiches atelier (WorkshopIntervention + Equipment + Client)."""
    query = (
        select(WorkshopIntervention, Equipment, Client.name.label("cn"))
        .join(Equipment, WorkshopIntervention.equipment_id == Equipment.id)
        .join(Client, Equipment.client_id == Client.id)
        .order_by(WorkshopIntervention.intervention_date.desc())
    )
    if client_id:
        query = query.where(Equipment.client_id == client_id)
    result = await db.execute(query)
    return [_atelier_combined(eq, interv, cn) for interv, eq, cn in result.all()]


@router.get("/{equipment_id}", response_model=dict)
async def get_equipment(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(eq.client_id)})
    return _eq_dict(eq, cr.scalar_one_or_none() or "")


@router.post("/", response_model=dict, status_code=201)
async def create_equipment(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    for field in ["id", "created_at", "updated_at", "client_name"]:
        data.pop(field, None)
    eq = Equipment(**data)
    db.add(eq)
    await db.flush()
    await db.refresh(eq)
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(eq.client_id)})
    return _eq_dict(eq, cr.scalar_one_or_none() or "")


@atelier_router.post("/", response_model=dict, status_code=201)
async def create_atelier_fiche(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Crée Equipment + WorkshopIntervention depuis le payload plat du Qt Atelier."""
    for f in ["id", "created_at", "updated_at", "client_name"]:
        data.pop(f, None)

    # Extraire les champs intervention (pas sur Equipment)
    qt_status      = data.pop("status", "diagnostic")
    description    = data.pop("description", "") or ""
    work_done      = data.pop("work_done", None)
    labor_hours    = float(data.pop("labor_hours", None) or 0) or None
    parts_cost     = float(data.pop("parts_cost", None) or 0) or None
    interv_type_qt = data.pop("intervention_type", "repair") or "repair"
    notes_extra    = data.pop("notes", None)

    # device_type → type
    if "device_type" in data:
        data["type"] = data.pop("device_type")

    # Qt status → Equipment status
    data["status"] = "in_repair" if qt_status not in ("done", "returned", "unrepairable") else "active"

    # Ne garder que les champs valides pour Equipment
    EQ_FIELDS = {"client_id", "site_id", "type", "brand", "model", "serial_number",
                 "asset_tag", "specs_json", "purchase_date", "warranty_until",
                 "nas_path", "notes", "status"}
    eq_data = {k: v for k, v in data.items() if k in EQ_FIELDS and v is not None}
    if description and not eq_data.get("notes"):
        eq_data["notes"] = description

    eq = Equipment(**eq_data)
    db.add(eq)
    await db.flush()

    # Créer WorkshopIntervention
    interv_type_mapped = INTERV_TYPE_MAP.get(interv_type_qt, "repair")
    extra = {
        "qt_status":   qt_status,
        "work_done":   work_done,
        "labor_hours": labor_hours,
        "parts_cost":  parts_cost,
        "notes":       notes_extra,
    }
    interv = WorkshopIntervention(
        equipment_id=eq.id,
        intervention_type=interv_type_mapped,
        intervention_date=date.today(),
        summary=description or None,
        checks_json=extra,
    )
    db.add(interv)
    await db.flush()
    await db.refresh(interv)

    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(eq.client_id)})
    return _atelier_combined(eq, interv, cr.scalar_one_or_none() or "")


@router.patch("/{equipment_id}", response_model=dict)
async def update_equipment(
    equipment_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    for field in ["id", "created_at", "updated_at", "client_name"]:
        data.pop(field, None)
    for key, value in data.items():
        if hasattr(eq, key):
            setattr(eq, key, value)
    await db.flush()
    await db.refresh(eq)
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(eq.client_id)})
    return _eq_dict(eq, cr.scalar_one_or_none() or "")


# ── Workshop interventions ─────────────────────────────────

@router.get("/{equipment_id}/interventions", response_model=list[dict])
async def list_workshop_interventions(
    equipment_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WorkshopIntervention)
        .where(WorkshopIntervention.equipment_id == equipment_id)
        .order_by(WorkshopIntervention.intervention_date.desc())
    )
    return [_intervention_dict(i) for i in result.scalars().all()]


@router.post("/{equipment_id}/interventions", response_model=dict, status_code=201)
async def create_workshop_intervention(
    equipment_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data["equipment_id"] = str(equipment_id)
    data.pop("id", None)
    if not data.get("intervention_date"):
        data["intervention_date"] = date.today().isoformat()
    intervention = WorkshopIntervention(**data)
    db.add(intervention)
    await db.flush()
    await db.refresh(intervention)
    return _intervention_dict(intervention)


@atelier_router.patch("/{interv_id}", response_model=dict)
async def update_atelier_fiche(
    interv_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Met à jour la fiche atelier (intervention + equipment)."""
    result = await db.execute(
        select(WorkshopIntervention, Equipment)
        .join(Equipment, WorkshopIntervention.equipment_id == Equipment.id)
        .where(WorkshopIntervention.id == interv_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Fiche introuvable")
    interv, eq = row

    for f in ["id", "created_at", "updated_at", "client_name", "equipment_id"]:
        data.pop(f, None)

    qt_status      = data.pop("status", None)
    description    = data.pop("description", None)
    work_done      = data.pop("work_done", None)
    labor_hours    = data.pop("labor_hours", None)
    parts_cost     = data.pop("parts_cost", None)
    interv_type_qt = data.pop("intervention_type", None)
    data.pop("notes", None)

    if "device_type" in data:
        eq.type = data.pop("device_type")
    if data.get("brand") is not None:   eq.brand  = data["brand"]
    if data.get("model") is not None:   eq.model  = data["model"]
    if data.get("serial_number") is not None: eq.serial_number = data["serial_number"]
    if qt_status:
        eq.status = "in_repair" if qt_status not in ("done", "returned", "unrepairable") else "active"

    if interv_type_qt:
        interv.intervention_type = INTERV_TYPE_MAP.get(interv_type_qt, "repair")
    if description is not None:
        interv.summary = description

    extra = interv.checks_json or {}
    if qt_status:     extra["qt_status"]   = qt_status
    if work_done:     extra["work_done"]   = work_done
    if labor_hours:   extra["labor_hours"] = float(labor_hours)
    if parts_cost:    extra["parts_cost"]  = float(parts_cost)
    interv.checks_json = extra

    await db.flush()

    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(eq.client_id)})
    return _atelier_combined(eq, interv, cr.scalar_one_or_none() or "")
