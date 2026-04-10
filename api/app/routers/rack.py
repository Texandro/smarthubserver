# -*- coding: utf-8 -*-
"""
SmartHub — Router As-Built Réseau (complet)
Endpoints catalogue + rack + patch panel + floor plan + PDF
"""
from __future__ import annotations
import uuid, os, io
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..auth import require_owner, get_current_user
from ..models.auth import User
from ..models.rack import (
    CatalogItem, RackDocument, RackDocumentVersion,
    RackConfig, RackEquipmentSlot, PatchPanelMapping, FloorPlan,
)

router = APIRouter()

# ── Helpers ───────────────────────────────────────────────────

def _ci(c: CatalogItem) -> dict:
    return {"id": str(c.id), "manufacturer": c.manufacturer, "model": c.model,
            "category": c.category, "height_u": c.height_u, "is_rackmount": c.is_rackmount,
            "port_count": c.port_count, "poe": c.poe, "poe_budget_w": c.poe_budget_w,
            "max_power_w": c.max_power_w, "notes": c.notes, "is_custom": c.is_custom}

def _slot(s: RackEquipmentSlot) -> dict:
    return {"id": str(s.id), "rack_id": str(s.rack_id),
            "catalog_item_id": str(s.catalog_item_id) if s.catalog_item_id else None,
            "catalog_item": _ci(s.catalog_item) if s.catalog_item else None,
            "position_u": s.position_u, "height_u": s.height_u,
            "hostname": s.hostname, "ip_address": s.ip_address,
            "mac_address": s.mac_address, "serial_number": s.serial_number,
            "role": s.role, "custom_manufacturer": s.custom_manufacturer,
            "custom_model": s.custom_model, "custom_category": s.custom_category}

def _port(p: PatchPanelMapping) -> dict:
    return {"id": str(p.id), "slot_id": str(p.slot_id),
            "port_number": p.port_number, "destination_label": p.destination_label,
            "cable_type": p.cable_type, "cable_length_m": float(p.cable_length_m) if p.cable_length_m else None,
            "connected_switch_port": p.connected_switch_port,
            "status": p.status, "notes": p.notes}

def _doc(d: RackDocument) -> dict:
    return {"id": str(d.id), "client_id": str(d.client_id), "title": d.title,
            "doc_type": d.doc_type, "status": d.status, "version": d.version,
            "notes": d.notes, "nas_path": d.nas_path,
            "created_at": d.created_at.isoformat(), "updated_at": d.updated_at.isoformat()}


# ── Catalogue matériel ────────────────────────────────────────

@router.get("/asbuilt/catalog/")
async def list_catalog(
    category: Optional[str] = None,
    manufacturer: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(CatalogItem)
    if category:     q = q.where(CatalogItem.category == category)
    if manufacturer: q = q.where(CatalogItem.manufacturer.ilike(f"%{manufacturer}%"))
    q = q.order_by(CatalogItem.manufacturer, CatalogItem.model)
    r = await db.execute(q)
    return [_ci(c) for c in r.scalars().all()]


@router.post("/asbuilt/catalog/", status_code=201)
async def create_catalog_item(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    for f in ["id", "created_at"]: data.pop(f, None)
    data["is_custom"]   = True
    data["created_by"]  = current_user.id
    item = CatalogItem(**data)
    db.add(item); await db.commit(); await db.refresh(item)
    return _ci(item)


# ── Documents réseau ──────────────────────────────────────────

@router.get("/asbuilt/rack/")
async def list_rack_docs(
    client_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(RackDocument)
    if client_id: q = q.where(RackDocument.client_id == client_id)
    q = q.order_by(RackDocument.updated_at.desc())
    r = await db.execute(q)
    return [_doc(d) for d in r.scalars().all()]


@router.post("/asbuilt/rack/", status_code=201)
async def create_rack_doc(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]: data.pop(f, None)
    data["created_by"] = current_user.id
    d = RackDocument(**data)
    db.add(d); await db.commit(); await db.refresh(d)

    # Créer rack config par défaut
    rc = RackConfig(document_id=d.id,
                    rack_size_u=data.get("rack_size_u", 12),
                    rack_label=data.get("rack_label", "Rack A"),
                    location=data.get("location"))
    db.add(rc)

    # Créer floor plan vide si full_cabinet
    if data.get("doc_type","full_cabinet") != "rack_only":
        fp = FloorPlan(document_id=d.id)
        db.add(fp)

    await db.commit()
    return _doc(d)


@router.get("/asbuilt/rack/{doc_id}")
async def get_rack_doc(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    r = await db.execute(
        select(RackDocument)
        .options(
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.catalog_item),
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.patch_ports),
            selectinload(RackDocument.floor_plans),
        )
        .where(RackDocument.id == doc_id)
    )
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404, "Document introuvable")

    result = _doc(d)
    result["rack_configs"] = []
    for rc in d.rack_configs:
        rc_dict = {"id": str(rc.id), "rack_size_u": rc.rack_size_u,
                   "rack_label": rc.rack_label, "location": rc.location}
        slots_list = []
        for s in sorted(rc.slots, key=lambda x: x.position_u):
            sd = _slot(s)
            sd["patch_ports"] = [_port(p) for p in sorted(s.patch_ports, key=lambda x: x.port_number)]
            slots_list.append(sd)
        rc_dict["slots"] = slots_list
        result["rack_configs"].append(rc_dict)

    result["floor_plans"] = []
    for fp in d.floor_plans:
        result["floor_plans"].append({
            "id": str(fp.id), "rooms": fp.rooms, "outlets": fp.outlets,
            "devices": fp.devices, "rack_position": fp.rack_position,
            "canvas_width": fp.canvas_width, "canvas_height": fp.canvas_height,
        })

    return result


@router.patch("/asbuilt/rack/{doc_id}")
async def update_rack_doc(doc_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(RackDocument).where(RackDocument.id == doc_id))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404, "Document introuvable")
    for f in ["id","client_id","created_at","updated_at"]: data.pop(f, None)
    for k, v in data.items(): setattr(d, k, v)
    await db.commit(); await db.refresh(d)
    return _doc(d)


@router.delete("/asbuilt/rack/{doc_id}", status_code=204)
async def delete_rack_doc(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(RackDocument).where(RackDocument.id == doc_id))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404, "Document introuvable")
    await db.delete(d); await db.commit()


# ── Publier nouvelle version + générer PDF ────────────────────

@router.post("/asbuilt/rack/{doc_id}/publish")
async def publish_rack_doc(
    doc_id: str,
    data: dict,   # {"version_note": "..."}
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_owner),
):
    r = await db.execute(
        select(RackDocument)
        .options(
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.catalog_item),
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.patch_ports),
            selectinload(RackDocument.floor_plans),
        )
        .where(RackDocument.id == doc_id)
    )
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404, "Document introuvable")

    # Récup client
    from ..models.client import Client
    cr = await db.execute(select(Client).where(Client.id == d.client_id))
    client = cr.scalar_one_or_none()
    client_name = client.name if client else "Client"

    # Construire les données pour le PDF
    rc = d.rack_configs[0] if d.rack_configs else None
    rack_data  = {"rack_size_u": rc.rack_size_u, "rack_label": rc.rack_label,
                  "location": rc.location} if rc else {}
    slots_data = []
    pp_data    = []

    if rc:
        for s in sorted(rc.slots, key=lambda x: x.position_u):
            sd = _slot(s)
            slots_data.append(sd)
            ci = s.catalog_item
            if ci and ci.category == "patch_panel":
                pp_data.append({
                    "slot": sd,
                    "ports": [_port(p) for p in sorted(s.patch_ports, key=lambda x: x.port_number)]
                })

    fp_data = None
    if d.floor_plans:
        fp = d.floor_plans[0]
        fp_data = {"rooms": fp.rooms, "outlets": fp.outlets,
                   "devices": fp.devices, "rack_position": fp.rack_position,
                   "canvas_width": fp.canvas_width, "canvas_height": fp.canvas_height}

    doc_data = _doc(d)

    # Générer PDF
    try:
        from ..services.rack_pdf import generate_rack_pdf
        pdf_bytes = generate_rack_pdf(
            document=doc_data, rack=rack_data, slots=slots_data,
            patch_panels=pp_data, floor_plan=fp_data, client_name=client_name
        )
    except Exception as e:
        raise HTTPException(500, f"Erreur génération PDF : {e}")

    # Sauver PDF sur NAS — même structure que documents.py
    NAS_BASE = os.environ.get("NAS_BASE_PATH", "/mnt/nas/smarthub/Clients")
    safe_client = client_name
    safe_title  = d.title.replace(" ", "_").replace("/", "_")
    nas_dir = os.path.join(NAS_BASE, safe_client, "3. As-built", "réseau", "historique")
    os.makedirs(nas_dir, exist_ok=True)
    pdf_name = f"{safe_title}_v{d.version}.pdf"
    pdf_path = os.path.join(nas_dir, pdf_name)
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
    # Chemin relatif pour open_pdf (comme documents.py)
    pdf_path_rel = pdf_path.replace(NAS_BASE, "").lstrip("/")

    # Archiver version
    ver_entry = RackDocumentVersion(
        document_id  = d.id,
        version      = d.version,
        nas_path     = pdf_path_rel,
        version_note = data.get("version_note",""),
        created_by   = current_user.id,
    )
    db.add(ver_entry)

    # Incrémenter version + publier
    d.version  += 1
    d.status    = "published"
    d.nas_path  = pdf_path_rel
    await db.commit()

    return {"version": d.version - 1, "nas_path": pdf_path_rel, "pdf_size": len(pdf_bytes)}


@router.get("/asbuilt/rack/{doc_id}/pdf")
async def download_rack_pdf(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(
        select(RackDocument)
        .options(
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.catalog_item),
            selectinload(RackDocument.rack_configs)
            .selectinload(RackConfig.slots)
            .selectinload(RackEquipmentSlot.patch_ports),
            selectinload(RackDocument.floor_plans),
        )
        .where(RackDocument.id == doc_id)
    )
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404)

    from ..models.client import Client
    cr = await db.execute(select(Client).where(Client.id == d.client_id))
    client = cr.scalar_one_or_none()

    rc = d.rack_configs[0] if d.rack_configs else None
    rack_data  = {"rack_size_u": rc.rack_size_u, "rack_label": rc.rack_label,
                  "location": rc.location} if rc else {}
    slots_data = [_slot(s) for s in (sorted(rc.slots, key=lambda x: x.position_u) if rc else [])]
    pp_data    = []
    if rc:
        for s in rc.slots:
            if s.catalog_item and s.catalog_item.category == "patch_panel":
                pp_data.append({"slot": _slot(s),
                                 "ports": [_port(p) for p in sorted(s.patch_ports, key=lambda x: x.port_number)]})

    fp_data = None
    if d.floor_plans:
        fp = d.floor_plans[0]
        fp_data = {"rooms": fp.rooms, "outlets": fp.outlets, "devices": fp.devices,
                   "rack_position": fp.rack_position,
                   "canvas_width": fp.canvas_width, "canvas_height": fp.canvas_height}

    from ..services.rack_pdf import generate_rack_pdf
    pdf_bytes = generate_rack_pdf(
        document=_doc(d), rack=rack_data, slots=slots_data,
        patch_panels=pp_data, floor_plan=fp_data,
        client_name=client.name if client else "Client"
    )

    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="asbuilt_{d.version}.pdf"'})


@router.get("/asbuilt/rack/{doc_id}/versions")
async def get_versions(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(
        select(RackDocumentVersion)
        .where(RackDocumentVersion.document_id == doc_id)
        .order_by(RackDocumentVersion.version.desc())
    )
    return [{"id": str(v.id), "version": v.version, "nas_path": v.nas_path,
             "version_note": v.version_note, "created_at": v.created_at.isoformat()}
            for v in r.scalars().all()]


# ── Rack config ───────────────────────────────────────────────

@router.get("/asbuilt/rack/{doc_id}/config")
async def get_rack_config(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(select(RackConfig).where(RackConfig.document_id == doc_id))
    rc = r.scalar_one_or_none()
    if not rc: raise HTTPException(404, "Config rack introuvable")
    return {"id": str(rc.id), "rack_size_u": rc.rack_size_u,
            "rack_label": rc.rack_label, "location": rc.location}


@router.patch("/asbuilt/rack/{doc_id}/config")
async def update_rack_config(doc_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(RackConfig).where(RackConfig.document_id == doc_id))
    rc = r.scalar_one_or_none()
    if not rc: raise HTTPException(404)
    for f in ["id","document_id","created_at","updated_at"]: data.pop(f, None)
    for k, v in data.items(): setattr(rc, k, v)
    await db.commit(); await db.refresh(rc)
    return {"id": str(rc.id), "rack_size_u": rc.rack_size_u,
            "rack_label": rc.rack_label, "location": rc.location}


# ── Slots équipements ─────────────────────────────────────────

@router.get("/asbuilt/rack/{doc_id}/slots")
async def list_slots(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(select(RackConfig).where(RackConfig.document_id == doc_id))
    rc = r.scalar_one_or_none()
    if not rc: raise HTTPException(404)
    r2 = await db.execute(
        select(RackEquipmentSlot)
        .options(selectinload(RackEquipmentSlot.catalog_item))
        .where(RackEquipmentSlot.rack_id == rc.id)
        .order_by(RackEquipmentSlot.position_u)
    )
    return [_slot(s) for s in r2.scalars().all()]


@router.post("/asbuilt/rack/{doc_id}/slots", status_code=201)
async def add_slot(doc_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(RackConfig).where(RackConfig.document_id == doc_id))
    rc = r.scalar_one_or_none()
    if not rc: raise HTTPException(404)

    for f in ["id","created_at","updated_at"]: data.pop(f, None)
    data["rack_id"] = str(rc.id)

    # Vérif chevauchement
    pos = data.get("position_u", 1)
    h   = data.get("height_u", 1)
    r2  = await db.execute(
        select(RackEquipmentSlot).where(RackEquipmentSlot.rack_id == rc.id)
    )
    existing = r2.scalars().all()
    for ex in existing:
        ex_end = ex.position_u + ex.height_u - 1
        new_end = pos + h - 1
        if not (new_end < ex.position_u or pos > ex_end):
            raise HTTPException(400,
                f"Chevauchement avec équipement en U{ex.position_u}")

    s = RackEquipmentSlot(**data)
    db.add(s); await db.commit()

    # Auto-créer les ports si patch panel
    await db.refresh(s)
    if data.get("catalog_item_id"):
        cr = await db.execute(select(CatalogItem).where(
            CatalogItem.id == data["catalog_item_id"]))
        ci = cr.scalar_one_or_none()
        if ci and ci.category == "patch_panel" and ci.port_count:
            for pn in range(1, ci.port_count + 1):
                port = PatchPanelMapping(slot_id=s.id, port_number=pn)
                db.add(port)
            await db.commit()

    await db.refresh(s)
    r3 = await db.execute(
        select(RackEquipmentSlot)
        .options(selectinload(RackEquipmentSlot.catalog_item))
        .where(RackEquipmentSlot.id == s.id)
    )
    return _slot(r3.scalar_one())


@router.patch("/asbuilt/slots/{slot_id}")
async def update_slot(slot_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(
        select(RackEquipmentSlot)
        .options(selectinload(RackEquipmentSlot.catalog_item))
        .where(RackEquipmentSlot.id == slot_id)
    )
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404)
    for f in ["id","rack_id","created_at","updated_at"]: data.pop(f, None)
    for k, v in data.items(): setattr(s, k, v)
    await db.commit(); await db.refresh(s)
    return _slot(s)


@router.delete("/asbuilt/slots/{slot_id}", status_code=204)
async def delete_slot(slot_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(RackEquipmentSlot).where(RackEquipmentSlot.id == slot_id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404)
    await db.delete(s); await db.commit()


# ── Patch panel ports ─────────────────────────────────────────

@router.get("/asbuilt/slots/{slot_id}/ports")
async def get_ports(slot_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(
        select(PatchPanelMapping)
        .where(PatchPanelMapping.slot_id == slot_id)
        .order_by(PatchPanelMapping.port_number)
    )
    return [_port(p) for p in r.scalars().all()]


@router.put("/asbuilt/slots/{slot_id}/ports")
async def save_ports(slot_id: str, payload: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    """Sauvegarde complète du mapping (upsert par port_number)."""
    ports = payload.get("ports", [])
    r = await db.execute(
        select(PatchPanelMapping).where(PatchPanelMapping.slot_id == slot_id))
    existing = {p.port_number: p for p in r.scalars().all()}

    for port_data in ports:
        pn = port_data.get("port_number")
        if not pn: continue
        if pn in existing:
            p = existing[pn]
            for k in ["destination_label","cable_type","cable_length_m",
                       "connected_switch_port","status","notes"]:
                if k in port_data:
                    setattr(p, k, port_data[k])
        else:
            p = PatchPanelMapping(slot_id=slot_id, **{
                k: port_data[k] for k in port_data
                if k not in ["id","created_at","updated_at","slot_id"]
            })
            db.add(p)

    await db.commit()
    r2 = await db.execute(
        select(PatchPanelMapping)
        .where(PatchPanelMapping.slot_id == slot_id)
        .order_by(PatchPanelMapping.port_number)
    )
    return [_port(p) for p in r2.scalars().all()]


# ── Floor plan ────────────────────────────────────────────────

@router.get("/asbuilt/rack/{doc_id}/floorplan")
async def get_floorplan(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(select(FloorPlan).where(FloorPlan.document_id == doc_id))
    fp = r.scalar_one_or_none()
    if not fp:
        return {"rooms": [], "outlets": [], "devices": [], "rack_position": None,
                "canvas_width": 800, "canvas_height": 600}
    return {"id": str(fp.id), "rooms": fp.rooms, "outlets": fp.outlets,
            "devices": fp.devices, "rack_position": fp.rack_position,
            "canvas_width": fp.canvas_width, "canvas_height": fp.canvas_height}


@router.put("/asbuilt/rack/{doc_id}/floorplan")
async def save_floorplan(doc_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(FloorPlan).where(FloorPlan.document_id == doc_id))
    fp = r.scalar_one_or_none()
    if not fp:
        fp = FloorPlan(document_id=doc_id)
        db.add(fp)
    for k in ["rooms","outlets","devices","rack_position","canvas_width","canvas_height"]:
        if k in data:
            setattr(fp, k, data[k])
    await db.commit(); await db.refresh(fp)
    return {"id": str(fp.id), "rooms": fp.rooms}
