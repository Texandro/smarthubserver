from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone, date

from ..core.database import get_db
from ..models.forensics import ForensicsCase, ForensicsEvidence, ForensicsStatus
from ..models.contract import Contract, ContractType, ContractStatus
from ..models.auth import User
from ..auth import require_owner

router = APIRouter(prefix="/forensics", tags=["forensics"])


def _case_dict(c: ForensicsCase, client_name: str = "") -> dict:
    return {
        "id":                   str(c.id),
        "client_id":            str(c.client_id),
        "client_name":          client_name,
        "contract_id":          str(c.contract_id),
        "case_reference":       c.case_reference,
        "reference":            c.case_reference,   # alias pour le Qt
        "title":                c.title,
        "mandat":               c.title,            # alias pour le Qt
        "objectives":           c.objectives,
        "scope":                c.scope,
        "status":               c.status,
        "phases_data":          c.phases_data or {},
        "opened_at":            c.opened_at.isoformat(),
        "closed_at":            c.closed_at.isoformat() if c.closed_at else None,
        "final_report_path":    c.final_report_path,
        "chain_of_custody_notes": c.chain_of_custody_notes,
        "created_at":           c.created_at.isoformat(),
    }


def _evidence_dict(e: ForensicsEvidence) -> dict:
    return {
        "id":               str(e.id),
        "case_id":          str(e.case_id),
        "evidence_number":  e.evidence_number,
        "description":      e.description,
        "type":             e.type,
        "serial_number":    e.serial_number,
        "hash_md5":         e.hash_md5,
        "hash_sha256":      e.hash_sha256,
        "acquisition_date": e.acquisition_date.isoformat(),
        "acquisition_tool": e.acquisition_tool,
        "storage_location": e.storage_location,
        "nas_path":         e.nas_path,
        "notes":            e.notes,
    }


# /forensics/ et /forensics/missions/ pointent vers les mêmes handlers

@router.get("/", response_model=list[dict])
@router.get("/missions/", response_model=list[dict])
async def list_cases(
    client_id : Optional[UUID] = None,
    status    : Optional[str]  = None,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(require_owner),
):
    query = select(ForensicsCase).order_by(ForensicsCase.opened_at.desc())
    if client_id:
        query = query.where(ForensicsCase.client_id == client_id)
    if status:
        query = query.where(ForensicsCase.status == status)
    result = await db.execute(query)
    cases = result.scalars().all()
    # Récupérer les noms clients
    out = []
    for c in cases:
        cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(c.client_id)})
        cn = cr.scalar_one_or_none() or ""
        out.append(_case_dict(c, cn))
    return out


@router.get("/{case_id}", response_model=dict)
async def get_case(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(select(ForensicsCase).where(ForensicsCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    evidence = await db.execute(
        select(ForensicsEvidence).where(ForensicsEvidence.case_id == case_id)
        .order_by(ForensicsEvidence.evidence_number)
    )
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(case.client_id)})
    d = _case_dict(case, cr.scalar_one_or_none() or "")
    d["evidence"] = [_evidence_dict(e) for e in evidence.scalars().all()]
    return d


@router.post("/", response_model=dict, status_code=201)
@router.post("/missions/", response_model=dict, status_code=201)
async def create_case(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    contract_id = data.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="Lettre de mission signée obligatoire (contract_id)")

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    if contract.contract_type != ContractType.lm_forensics:
        raise HTTPException(status_code=400, detail=f"Le contrat doit être de type lm_forensics")
    if contract.status not in [ContractStatus.signé, ContractStatus.actif]:
        raise HTTPException(status_code=400, detail=f"La LM doit être signée (statut: {contract.status})")

    for field in ["id", "created_at", "updated_at", "client_name", "reference", "mandat"]:
        data.pop(field, None)

    if not data.get("case_reference"):
        count = await db.execute(select(ForensicsCase).where(ForensicsCase.client_id == data["client_id"]))
        seq = len(count.scalars().all()) + 1
        data["case_reference"] = f"FOR-{date.today().year}-{str(seq).zfill(3)}"

    case = ForensicsCase(**data)
    db.add(case)
    await db.flush()
    await db.refresh(case)
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(case.client_id)})
    return _case_dict(case, cr.scalar_one_or_none() or "")


@router.patch("/{case_id}", response_model=dict)
async def update_case(
    case_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(select(ForensicsCase).where(ForensicsCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Dossier introuvable")

    if data.get("status") == "clôturé" and not case.closed_at:
        case.closed_at = datetime.now(timezone.utc)

    for field in ["id", "created_at", "updated_at", "client_name", "reference", "mandat"]:
        data.pop(field, None)

    for key, value in data.items():
        if hasattr(case, key):
            setattr(case, key, value)
    await db.flush()
    await db.refresh(case)
    cr = await db.execute(text("SELECT name FROM clients WHERE id=:id"), {"id": str(case.client_id)})
    return _case_dict(case, cr.scalar_one_or_none() or "")


@router.post("/{case_id}/evidence", response_model=dict, status_code=201)
async def add_evidence(
    case_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    data["case_id"] = str(case_id)
    data.pop("id", None)
    if not data.get("acquisition_date"):
        data["acquisition_date"] = datetime.now(timezone.utc)
    evidence = ForensicsEvidence(**data)
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return _evidence_dict(evidence)
