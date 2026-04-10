# -*- coding: utf-8 -*-
"""
SmartHub — Router Documents
Upload de fichiers vers le NAS dans le dossier du client.
"""
import os, shutil, re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from ..core.database import get_db
from ..models.client import Client
from ..models.auth import User
from ..auth import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])

NAS_BASE = os.environ.get("NAS_BASE_PATH", "/mnt/nas/smarthub/Clients")

FOLDER_MAP = {
    "contrat":   "0. Contrats signés",
    "facture":   "1. Factures",
    "rapport":   "2. Rapports",
    "forensics": "5. Forensics",
    "divers":    "6. Divers",
}


def _safe_name(s: str) -> str:
    s = re.sub(r'[<>:"/\\|?*]', '_', s)
    return s.strip().rstrip('.')[:80]


@router.post("/upload")
async def upload_document(
    client_id: UUID       = Form(...),
    category:  str        = Form("contrat"),
    filename:  str        = Form(...),
    file:      UploadFile = File(...),
    db:        AsyncSession = Depends(get_db),
    _:         User         = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client introuvable")

    client_dir = os.path.join(NAS_BASE, _safe_name(client.name))
    if not os.path.isdir(client_dir):
        raise HTTPException(404, f"Dossier NAS introuvable : {client_dir}")

    sub      = FOLDER_MAP.get(category, "6. Divers")
    dest_dir = os.path.join(client_dir, sub)
    os.makedirs(dest_dir, exist_ok=True)

    safe_fn = _safe_name(filename)
    if not safe_fn.endswith(".pdf"):
        safe_fn += ".pdf"
    dest_path = os.path.join(dest_dir, safe_fn)

    # Éviter l'écrasement
    if os.path.exists(dest_path):
        base, ext = os.path.splitext(safe_fn)
        i = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(dest_dir, f"{base}_{i}{ext}")
            i += 1

    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {
        "success":   True,
        "path":      dest_path,
        "nas_path":  dest_path.replace(NAS_BASE, "").lstrip("/"),
        "filename":  os.path.basename(dest_path),
        "client_id": str(client_id),
        "category":  category,
    }


@router.get("/download")
async def download_document(
    path: str,
    _: User = Depends(get_current_user),
):
    """
    Télécharge un fichier depuis le NAS.
    path = chemin relatif depuis NAS_BASE, ex: Smartclick/0. Contrats signés/LM-IT-S-2026-001.pdf
    """
    import urllib.parse
    full_path = os.path.join(NAS_BASE, path.lstrip("/"))
    # Sécurité : rester dans NAS_BASE
    if not os.path.abspath(full_path).startswith(os.path.abspath(NAS_BASE)):
        raise HTTPException(403, "Accès interdit")
    if not os.path.isfile(full_path):
        raise HTTPException(404, f"Fichier introuvable : {path}")
    from fastapi.responses import FileResponse
    return FileResponse(
        full_path,
        media_type="application/pdf",
        filename=os.path.basename(full_path),
    )


@router.get("/contract/{contract_id}")
async def get_contract_documents(
    contract_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Retourne les documents liés à un contrat (cherche par référence dans le NAS)."""
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT c.reference, cl.name as client_name FROM contracts c "
             "JOIN clients cl ON cl.id = c.client_id WHERE c.id = :cid"),
        {"cid": contract_id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(404, "Contrat introuvable")

    ref, client_name = row.reference, row.client_name
    client_dir = os.path.join(NAS_BASE, _safe_name(client_name))
    docs = []
    for folder_key, folder_name in FOLDER_MAP.items():
        folder_path = os.path.join(client_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        for fname in sorted(os.listdir(folder_path)):
            if ref and ref.lower() in fname.lower():
                fpath = os.path.join(folder_path, fname)
                nas_rel = fpath.replace(NAS_BASE, "").lstrip("/")
                docs.append({
                    "filename": fname,
                    "category": folder_key,
                    "folder":   folder_name,
                    "size":     os.path.getsize(fpath),
                    "nas_path": nas_rel,
                })
    return {"documents": docs, "reference": ref, "client_name": client_name}


@router.get("/client/{client_id}")
async def list_documents(
    client_id: UUID,
    db:        AsyncSession = Depends(get_db),
    _:         User = Depends(get_current_user),
):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(404, "Client introuvable")

    client_dir = os.path.join(NAS_BASE, _safe_name(client.name))
    if not os.path.isdir(client_dir):
        return {"documents": [], "client_dir": client_dir}

    docs = []
    for folder_key, folder_name in FOLDER_MAP.items():
        folder_path = os.path.join(client_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue
        for fname in sorted(os.listdir(folder_path)):
            fpath = os.path.join(folder_path, fname)
            if os.path.isfile(fpath):
                docs.append({
                    "filename": fname,
                    "category": folder_key,
                    "folder":   folder_name,
                    "size":     os.path.getsize(fpath),
                    "modified": os.path.getmtime(fpath),
                })
    return {"documents": docs, "client_dir": client_dir}
