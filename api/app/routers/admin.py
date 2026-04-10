"""
SmartHub — Router Admin
Endpoints de maintenance : vérification NAS, regénération PDF.
"""
import os
import re
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..models.client import Client
from ..models.contract import Contract, ContractType
from ..models.auth import User
from ..auth import require_owner
from .nas import create_client_structure

router = APIRouter(prefix="/admin", tags=["admin"])

NAS_BASE = Path(os.getenv("NAS_BASE_PATH", "/mnt/nas/smarthub/Clients"))


def _safe_name(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', '-', name)
    return name.strip('. ')[:80]


@router.post("/check-nas", response_model=dict)
async def check_nas(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """Vérifie/crée l'arborescence NAS pour chaque client en base."""
    import asyncio

    result = await db.execute(select(Client).order_by(Client.name))
    clients = result.scalars().all()

    already_ok = 0
    created = 0
    failed = 0
    errors: list[str] = []

    loop = asyncio.get_event_loop()
    for client in clients:
        folder = NAS_BASE / _safe_name(client.name)
        if folder.exists():
            already_ok += 1
            continue

        nas = await loop.run_in_executor(None, create_client_structure, client.name)
        if nas["success"]:
            created += 1
            if not client.nas_path:
                client.nas_path = nas.get("nas_path", nas["path"])
        else:
            failed += 1
            errors.append(f"{client.name}: {nas.get('error', 'unknown')}")

    if created:
        await db.flush()

    return {
        "total_clients": len(clients),
        "already_ok": already_ok,
        "created": created,
        "failed": failed,
        "errors": errors,
    }


@router.post("/regen-pdfs", response_model=dict)
async def regen_pdfs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """Vérifie chaque contrat et regénère le PDF s'il manque sur le NAS."""
    from ..services.contract_pdf import generate_lm, generate_maintenance

    result = await db.execute(
        select(Contract)
        .options(selectinload(Contract.items))
        .order_by(Contract.created_at.desc())
    )
    contracts = result.scalars().all()

    # Pré-fetch tous les clients en une query
    client_ids = {c.client_id for c in contracts}
    if client_ids:
        cr = await db.execute(select(Client).where(Client.id.in_(client_ids)))
        clients_map = {c.id: c for c in cr.scalars().all()}
    else:
        clients_map = {}

    already_ok = 0
    regenerated = 0
    failed = 0
    errors: list[str] = []

    for contract in contracts:
        client = clients_map.get(contract.client_id)
        if not client:
            failed += 1
            errors.append(f"{contract.reference}: client introuvable")
            continue

        safe = _safe_name(client.name)
        pdf_path = NAS_BASE / safe / "0. Contrats signés" / f"{contract.reference}.pdf"

        if pdf_path.exists():
            already_ok += 1
            continue

        # Construire le payload
        contract._client_name = client.name
        from .contracts import _contract_dict
        data = _contract_dict(contract)
        data["client_name"] = client.name
        data["client_address"] = client.address or ""
        data["client_vat"] = client.vat_number or ""

        try:
            if contract.contract_type == ContractType.maintenance:
                pdf_bytes = generate_maintenance(data)
            else:
                pdf_bytes = generate_lm(data)
        except Exception as e:
            failed += 1
            errors.append(f"{contract.reference}: génération échouée — {e}")
            continue

        try:
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(pdf_bytes)
            regenerated += 1
        except Exception as e:
            failed += 1
            errors.append(f"{contract.reference}: écriture NAS échouée — {e}")

    return {
        "total_contracts": len(contracts),
        "already_ok": already_ok,
        "regenerated": regenerated,
        "failed": failed,
        "errors": errors,
    }
