"""
SmartHub — Router Clients
Inclut les endpoints fiche 360° (contrats, interventions, sessions, forensics, atelier par client)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, text
from uuid import UUID
from typing import Optional

from ..core.database import get_db
from ..models.client import Client, Site, Contact, ClientStatus
from ..models.auth import User, UserRole
from ..auth import get_current_user, require_owner

router = APIRouter(prefix="/clients", tags=["clients"])


# ── Helpers ────────────────────────────────────────────────

def _client_dict(c: Client) -> dict:
    return {
        "id":               str(c.id),
        "name":             c.name,
        "status":           c.status,
        "client_type":      c.client_type,
        "vat_number":       c.vat_number,
        "address":          c.address,
        "phone":            c.phone,
        "email":            c.email,
        "nas_path":         c.nas_path,
        "falco_customer_id":c.falco_customer_id,
        "notes":            c.notes,
        "inactive_reason":  c.inactive_reason,
        "outstanding_debt": float(c.outstanding_debt) if c.outstanding_debt else 0,
        "created_at":       c.created_at.isoformat(),
        "updated_at":       c.updated_at.isoformat(),
    }

def _site_dict(s: Site) -> dict:
    return {
        "id":         str(s.id),
        "client_id":  str(s.client_id),
        "name":       s.name,
        "address":    s.address,
        "nas_path":   s.nas_path,
        "is_primary": s.is_primary,
        "notes":      s.notes,
        "created_at": s.created_at.isoformat(),
    }

def _contact_dict(c: Contact) -> dict:
    return {
        "id":         str(c.id),
        "client_id":  str(c.client_id),
        "site_id":    str(c.site_id) if c.site_id else None,
        "first_name": c.first_name,
        "last_name":  c.last_name,
        "email":      c.email,
        "phone":      c.phone,
        "role":       c.role,
        "is_primary": c.is_primary,
        "notes":      c.notes,
        "created_at": c.created_at.isoformat(),
    }


# ── CLIENTS ────────────────────────────────────────────────

@router.get("/", response_model=list[dict])
async def list_clients(
    status:  Optional[str] = None,
    search:  Optional[str] = None,
    skip:    int = 0,
    limit:   int = 100,
    db:      AsyncSession = Depends(get_db),
    _:       User = Depends(get_current_user),
):
    query = select(Client)
    if status:
        query = query.where(Client.status == status)
    if search:
        query = query.where(or_(
            Client.name.ilike(f"%{search}%"),
            Client.vat_number.ilike(f"%{search}%"),
            Client.email.ilike(f"%{search}%"),
        ))
    query = query.order_by(Client.name).offset(skip).limit(limit)
    result = await db.execute(query)
    return [_client_dict(c) for c in result.scalars().all()]


@router.get("/summary", response_model=list[dict])
async def list_clients_summary(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Version légère pour dropdowns — overlay timer, formulaires."""
    query = select(Client).order_by(Client.name)
    if active_only:
        query = query.where(Client.status == ClientStatus.actif)
    result = await db.execute(query)
    return [
        {"id": str(c.id), "name": c.name, "status": c.status, "client_type": c.client_type}
        for c in result.scalars().all()
    ]


@router.get("/{client_id}", response_model=dict)
async def get_client(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    d = _client_dict(client)
    # Sites + contacts inline
    sites    = await db.execute(select(Site).where(Site.client_id == client_id))
    contacts = await db.execute(select(Contact).where(Contact.client_id == client_id))
    d["sites"]    = [_site_dict(s) for s in sites.scalars().all()]
    d["contacts"] = [_contact_dict(c) for c in contacts.scalars().all()]
    return d


@router.post("/", response_model=dict, status_code=201)
async def create_client(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    data.pop("id", None)
    data.pop("created_at", None)
    data.pop("updated_at", None)
    client = Client(**data)
    db.add(client)
    await db.flush()
    await db.refresh(client)

    result = _client_dict(client)

    # Créer la structure NAS dans un thread séparé (évite MissingGreenlet)
    import asyncio
    from .nas import create_client_structure
    loop = asyncio.get_event_loop()
    nas = await loop.run_in_executor(None, create_client_structure, client.name)
    if nas["success"] and not client.nas_path:
        client.nas_path = nas.get("nas_path", nas["path"])
        await db.flush()
        result["nas_path"] = client.nas_path

    result["nas_created"] = nas["success"]
    result["nas_error"]   = nas.get("error")
    result["warnings"]    = [] if nas["success"] else [
        f"NAS indisponible — dossier non créé ({nas.get('error', 'unknown')}). "
        "Utilisez POST /clients/{id}/retry-nas pour réessayer."
    ]
    return result


@router.patch("/{client_id}", response_model=dict)
async def update_client(
    client_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")
    for key in ["id", "created_at", "updated_at"]:
        data.pop(key, None)
    for key, value in data.items():
        if hasattr(client, key):
            setattr(client, key, value)
    await db.flush()
    await db.refresh(client)
    return _client_dict(client)


@router.post("/{client_id}/retry-nas", response_model=dict)
async def retry_nas(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """Retente la création de la structure NAS pour un client."""
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    import asyncio
    from .nas import create_client_structure
    loop = asyncio.get_event_loop()
    nas = await loop.run_in_executor(None, create_client_structure, client.name)
    if nas["success"] and not client.nas_path:
        client.nas_path = nas.get("nas_path", nas["path"])
        await db.flush()

    return {
        "client_id":   str(client_id),
        "client_name": client.name,
        "nas_created": nas["success"],
        "nas_path":    nas.get("nas_path", nas.get("path")),
        "nas_error":   nas.get("error"),
    }


# ── FICHE 360° — données consolidées par client ────────────

@router.get("/{client_id}/contracts", response_model=list[dict])
async def client_contracts(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Contrats d'un client — réservé owner."""
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=403, detail="Accès réservé")
    result = await db.execute(text("""
        SELECT id, reference, title, contract_type, status, billing_type,
               start_date, end_date, sold_hours, sold_budget, monthly_amount,
               signed_at, created_at
        FROM contracts WHERE client_id = :cid ORDER BY created_at DESC
    """), {"cid": str(client_id)})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/interventions", response_model=list[dict])
async def client_interventions(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT id, titre, status, planned_at, started_at, ended_at,
               elapsed_min, technicien, is_billable, created_at
        FROM on_site_interventions
        WHERE client_id = :cid ORDER BY created_at DESC
    """), {"cid": str(client_id)})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/timetrack", response_model=list[dict])
async def client_timetrack(
    client_id: UUID,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT id, activity, started_at, ended_at, duration_minutes,
               amount, is_billable, is_included_in_contract, tags
        FROM time_sessions
        WHERE client_id = :cid
        ORDER BY started_at DESC LIMIT :lim
    """), {"cid": str(client_id), "lim": limit})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/projects", response_model=list[dict])
async def client_projects(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT p.id, p.title, p.status, p.priority, p.due_date,
               p.estimated_hours, p.waiting_for, kc.name AS kanban_column,
               p.created_at, p.updated_at
        FROM projects p
        LEFT JOIN kanban_columns kc ON kc.id = p.kanban_column_id
        WHERE p.client_id = :cid AND p.status != 'archived'
        ORDER BY p.updated_at DESC
    """), {"cid": str(client_id)})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/forensics", response_model=list[dict])
async def client_forensics(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.owner:
        raise HTTPException(status_code=403, detail="Accès réservé")
    result = await db.execute(text("""
        SELECT id, case_reference, title, status, opened_at, closed_at,
               final_report_path, created_at
        FROM forensics_cases WHERE client_id = :cid ORDER BY opened_at DESC
    """), {"cid": str(client_id)})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/atelier", response_model=list[dict])
async def client_atelier(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT wi.id, e.brand, e.model, e.serial_number, e.type AS equipment_type,
               wi.intervention_type, wi.intervention_date, wi.technician,
               wi.summary, wi.is_billable, wi.created_at
        FROM workshop_interventions wi
        JOIN equipment e ON e.id = wi.equipment_id
        WHERE e.client_id = :cid
        ORDER BY wi.intervention_date DESC
    """), {"cid": str(client_id)})
    return [dict(r) for r in result.mappings().all()]


@router.get("/{client_id}/activity", response_model=list[dict])
async def client_activity(
    client_id: UUID,
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Journal d'activité chronologique du client."""
    result = await db.execute(text("""
        SELECT id, log_type, title, description, source_type, source_id, created_at
        FROM activity_log WHERE client_id = :cid
        ORDER BY created_at DESC LIMIT :lim
    """), {"cid": str(client_id), "lim": limit})
    return [dict(r) for r in result.mappings().all()]


# ── SITES ──────────────────────────────────────────────────

@router.get("/{client_id}/sites", response_model=list[dict])
async def list_sites(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Site).where(Site.client_id == client_id))
    return [_site_dict(s) for s in result.scalars().all()]


@router.post("/{client_id}/sites", response_model=dict, status_code=201)
async def create_site(
    client_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    data.pop("id", None)
    site = Site(client_id=client_id, **{k: v for k, v in data.items() if k != "client_id"})
    db.add(site)
    await db.flush()
    await db.refresh(site)
    return _site_dict(site)


@router.patch("/{client_id}/sites/{site_id}", response_model=dict)
async def update_site(
    client_id: UUID,
    site_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(select(Site).where(Site.id == site_id, Site.client_id == client_id))
    site = result.scalar_one_or_none()
    if not site:
        raise HTTPException(status_code=404, detail="Site introuvable")
    for key, value in data.items():
        if hasattr(site, key) and key not in ["id", "client_id", "created_at"]:
            setattr(site, key, value)
    await db.flush()
    await db.refresh(site)
    return _site_dict(site)


# ── CONTACTS ───────────────────────────────────────────────

@router.get("/{client_id}/contacts", response_model=list[dict])
async def list_contacts(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Contact).where(Contact.client_id == client_id))
    return [_contact_dict(c) for c in result.scalars().all()]


@router.post("/{client_id}/contacts", response_model=dict, status_code=201)
async def create_contact(
    client_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    data.pop("id", None)
    contact = Contact(client_id=client_id, **{k: v for k, v in data.items() if k != "client_id"})
    db.add(contact)
    await db.flush()
    await db.refresh(contact)
    return _contact_dict(contact)


@router.delete("/{client_id}/contacts/{contact_id}", status_code=204)
async def delete_contact(
    client_id: UUID,
    contact_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id, Contact.client_id == client_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact introuvable")
    await db.delete(contact)
