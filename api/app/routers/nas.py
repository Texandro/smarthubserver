"""
SmartHub — Router NAS
Crée automatiquement la structure de dossiers sur le NAS à la création d'un client.

Structure créée : NAS/smarthub/Clients/{NomClient}/
    0. Contrats signes / 1. Factures / 2. Rapports /
    3. As-built/{Reseau,Logiciel,Autre} /
    4. Atelier/HD Shredding / 5. Forensics / 6. Divers
"""
import os, re
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from uuid import UUID

from ..core.database import get_db
from ..models.auth import User
from ..auth import require_owner

router = APIRouter(prefix="/nas", tags=["nas"])

NAS_BASE = Path(os.getenv("NAS_BASE_PATH", "/mnt/nas/smarthub/Clients"))

FOLDER_STRUCTURE = [
    "0. Contrats signés",
    "1. Factures",
    "2. Rapports",
    "3. As-built/Réseau",
    "3. As-built/Logiciel",
    "3. As-built/Autre",
    "4. Atelier/HD Shredding",
    "5. Forensics",
    "6. Divers",
]


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '-', name)
    return name.strip('. ')[:80]


def _client_folder(client_name: str) -> Path:
    return NAS_BASE / _safe_name(client_name)


def create_client_structure(client_name: str) -> dict:
    if not NAS_BASE.exists():
        return {"success": False, "path": str(_client_folder(client_name)),
                "folders_created": 0,
                "error": f"NAS non monté : {NAS_BASE} introuvable. Monter le share d'abord."}

    root = _client_folder(client_name)
    created = 0
    try:
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True); created += 1
        for sub in FOLDER_STRUCTURE:
            p = root / sub
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True); created += 1
        nas_path = str(root).replace("/mnt/nas", "\\\\NAS")
        return {"success": True, "path": str(root), "nas_path": nas_path,
                "folders_created": created, "error": None}
    except Exception as e:
        return {"success": False, "path": str(root),
                "folders_created": created, "error": str(e)}


@router.post("/clients/{client_id}/create-folders", response_model=dict)
async def create_folders(
    client_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(
        text("SELECT id, name, nas_path FROM clients WHERE id = :id"),
        {"id": str(client_id)})
    client = result.mappings().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    nas = create_client_structure(client["name"])

    if nas["success"] and not client["nas_path"]:
        await db.execute(
            text("UPDATE clients SET nas_path = :p WHERE id = :id"),
            {"p": nas.get("nas_path", nas["path"]), "id": str(client_id)})

    return {"client_id": str(client_id), "client_name": client["name"], **nas}


@router.get("/clients/{client_id}/browse", response_model=list[dict])
async def browse_client_folder(
    client_id: UUID,
    sub_path: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(
        text("SELECT name FROM clients WHERE id = :id"), {"id": str(client_id)})
    client = result.mappings().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client introuvable")

    root   = _client_folder(client["name"])
    target = (root / sub_path).resolve() if sub_path else root

    if not str(target).startswith(str(root)):
        raise HTTPException(status_code=400, detail="Chemin invalide")
    if not target.exists():
        return []

    items = []
    for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name)):
        items.append({
            "name":     entry.name,
            "is_dir":   entry.is_dir(),
            "size":     entry.stat().st_size if entry.is_file() else None,
            "modified": entry.stat().st_mtime,
            "path":     str(entry.relative_to(root)),
            "nas_path": str(entry).replace("/mnt/nas", "\\\\NAS"),
        })
    return items


@router.get("/status", response_model=dict)
async def nas_status(_: User = Depends(require_owner)):
    mounted = NAS_BASE.exists()
    writable = False
    if mounted:
        try:
            t = NAS_BASE / ".smarthub_test"; t.touch(); t.unlink(); writable = True
        except Exception:
            pass
    return {"mounted": mounted, "writable": writable,
            "path": str(NAS_BASE),
            "nas_share": str(NAS_BASE).replace("/mnt/nas", "\\\\NAS")}
