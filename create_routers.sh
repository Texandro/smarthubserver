#!/bin/bash
set -e
echo '🔧 Création des routers API...'

cat > /srv/smarthub/api/app/routers/contracts.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional
from datetime import date

from ..core.database import get_db
from ..models.contract import Contract, ContractItem, ContractType, ContractStatus, BillingType
from ..models.client import Client

router = APIRouter(prefix="/contracts", tags=["contracts"])


def generate_reference(contract_type: ContractType, client_name: str, year: int, seq: int) -> str:
    prefixes = {
        ContractType.maintenance: "CM",
        ContractType.lm_forensics: "LM-FOR",
        ContractType.lm_datashredding: "LM-DS",
        ContractType.lm_dev: "DEV",
        ContractType.lm_it_management: "LM-IT",
        ContractType.devis: "DEV",
        ContractType.autre: "CTR",
    }
    prefix = prefixes.get(contract_type, "CTR")
    slug = "".join(c for c in client_name.upper()[:3] if c.isalpha())
    return f"{prefix}-{slug}-{year}-{str(seq).zfill(3)}"


@router.get("/", response_model=list[dict])
async def list_contracts(
    client_id: Optional[UUID] = None,
    status: Optional[ContractStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Contract).options(selectinload(Contract.items))
    if client_id:
        query = query.where(Contract.client_id == client_id)
    if status:
        query = query.where(Contract.status == status)
    query = query.order_by(Contract.created_at.desc())
    result = await db.execute(query)
    contracts = result.scalars().all()
    return [_contract_to_dict(c) for c in contracts]


@router.get("/renewal-alerts", response_model=list[dict])
async def renewal_alerts(db: AsyncSession = Depends(get_db)):
    """Contrats qui arrivent à expiration selon renewal_reminder_days."""
    from sqlalchemy import text
    result = await db.execute(text("""
        SELECT c.id, c.reference, c.title, c.end_date,
               c.end_date - CURRENT_DATE AS days_until_expiry,
               cl.name AS client_name
        FROM contracts c
        JOIN clients cl ON cl.id = c.client_id
        WHERE c.end_date IS NOT NULL
          AND c.status = 'actif'
          AND c.end_date - CURRENT_DATE <= c.renewal_reminder_days
        ORDER BY days_until_expiry ASC
    """))
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/profitability", response_model=list[dict])
async def profitability(
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db)
):
    """Vue rentabilité — heures prestées vs budget vendu."""
    from sqlalchemy import text
    q = """
        SELECT contract_id, reference, title, client_name, contract_type,
               billing_type, sold_budget, sold_hours, hourly_rate, monthly_amount,
               start_date, end_date, status,
               hours_worked, amount_billable, amount_included, amount_overage,
               hours_remaining, budget_remaining
        FROM v_contract_profitability
        WHERE 1=1
    """
    params = {}
    if client_id:
        q += " AND client_id = :client_id"
        params["client_id"] = str(client_id)
    q += " ORDER BY start_date DESC"
    result = await db.execute(text(q), params)
    rows = result.mappings().all()
    return [dict(r) for r in rows]


@router.get("/{contract_id}", response_model=dict)
async def get_contract(contract_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items))
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    return _contract_to_dict(contract)


@router.post("/", response_model=dict, status_code=201)
async def create_contract(data: dict, db: AsyncSession = Depends(get_db)):
    # Génération référence automatique
    if "reference" not in data or not data["reference"]:
        result = await db.execute(select(Client).where(Client.id == data["client_id"]))
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client introuvable")
        year = date.today().year
        count_result = await db.execute(
            select(Contract).where(
                Contract.client_id == data["client_id"],
                Contract.contract_type == data["contract_type"]
            )
        )
        seq = len(count_result.scalars().all()) + 1
        data["reference"] = generate_reference(
            ContractType(data["contract_type"]), client.name, year, seq
        )

    items_data = data.pop("items", [])
    contract = Contract(**data)
    db.add(contract)
    await db.flush()

    for item in items_data:
        db.add(ContractItem(contract_id=contract.id, **item))

    await db.flush()
    await db.refresh(contract)
    return _contract_to_dict(contract)


@router.patch("/{contract_id}", response_model=dict)
async def update_contract(contract_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    for key, value in data.items():
        if hasattr(contract, key):
            setattr(contract, key, value)
    await db.flush()
    await db.refresh(contract)
    return _contract_to_dict(contract)


def _contract_to_dict(c: Contract) -> dict:
    return {
        "id": str(c.id),
        "client_id": str(c.client_id),
        "site_id": str(c.site_id) if c.site_id else None,
        "contract_type": c.contract_type,
        "reference": c.reference,
        "title": c.title,
        "status": c.status,
        "billing_type": c.billing_type,
        "start_date": c.start_date.isoformat() if c.start_date else None,
        "end_date": c.end_date.isoformat() if c.end_date else None,
        "renewal_reminder_days": c.renewal_reminder_days,
        "sold_hours": float(c.sold_hours) if c.sold_hours else None,
        "sold_budget": float(c.sold_budget) if c.sold_budget else None,
        "hourly_rate": float(c.hourly_rate) if c.hourly_rate else None,
        "monthly_amount": float(c.monthly_amount) if c.monthly_amount else None,
        "signed_at": c.signed_at.isoformat() if c.signed_at else None,
        "signed_by_name": c.signed_by_name,
        "notes": c.notes,
        "created_at": c.created_at.isoformat(),
        "items": [
            {
                "id": str(i.id),
                "description": i.description,
                "unit_price": float(i.unit_price) if i.unit_price else None,
                "quantity": float(i.quantity),
                "unit": i.unit,
                "is_included": i.is_included,
                "position": i.position,
            } for i in (c.items or [])
        ]
    }

HEREDOC

cat > /srv/smarthub/api/app/routers/projects.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional

from ..core.database import get_db
from ..models.project import Project, KanbanColumn, ProjectStatus, ProjectPriority

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/kanban", response_model=list[dict])
async def get_kanban(db: AsyncSession = Depends(get_db)):
    """Toutes les colonnes avec leurs projets — vue Kanban complète."""
    cols_result = await db.execute(
        select(KanbanColumn).order_by(KanbanColumn.position)
    )
    columns = cols_result.scalars().all()

    result = []
    for col in columns:
        proj_result = await db.execute(
            select(Project)
            .where(Project.kanban_column_id == col.id, Project.status != ProjectStatus.archived)
            .order_by(Project.priority.desc(), Project.updated_at.desc())
        )
        projects = proj_result.scalars().all()
        result.append({
            "id": str(col.id),
            "name": col.name,
            "color": col.color,
            "position": col.position,
            "auto_escalate_days": col.auto_escalate_days,
            "projects": [_project_to_dict(p) for p in projects]
        })
    return result


@router.get("/waiting", response_model=list[dict])
async def get_waiting(db: AsyncSession = Depends(get_db)):
    """Projets en attente tiers — depuis la vue SQL."""
    result = await db.execute(text("""
        SELECT id, title, status, priority, waiting_for, waiting_since,
               auto_remind_days, days_waiting, needs_reminder,
               client_name, kanban_column
        FROM v_projects_waiting
        ORDER BY days_waiting DESC
    """))
    return [dict(r) for r in result.mappings().all()]


@router.get("/", response_model=list[dict])
async def list_projects(
    client_id: Optional[UUID] = None,
    status: Optional[ProjectStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Project).where(Project.status != ProjectStatus.archived)
    if client_id:
        query = query.where(Project.client_id == client_id)
    if status:
        query = query.where(Project.status == status)
    query = query.order_by(Project.updated_at.desc())
    result = await db.execute(query)
    return [_project_to_dict(p) for p in result.scalars().all()]


@router.get("/{project_id}", response_model=dict)
async def get_project(project_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    return _project_to_dict(project)


@router.post("/", response_model=dict, status_code=201)
async def create_project(data: dict, db: AsyncSession = Depends(get_db)):
    # Auto-assign première colonne kanban si pas spécifié
    if "kanban_column_id" not in data or not data["kanban_column_id"]:
        col = await db.execute(select(KanbanColumn).order_by(KanbanColumn.position).limit(1))
        first_col = col.scalar_one_or_none()
        if first_col:
            data["kanban_column_id"] = str(first_col.id)
    project = Project(**data)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return _project_to_dict(project)


@router.patch("/{project_id}", response_model=dict)
async def update_project(project_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    for key, value in data.items():
        if hasattr(project, key):
            setattr(project, key, value)
    await db.flush()
    await db.refresh(project)
    return _project_to_dict(project)


@router.patch("/{project_id}/move", response_model=dict)
async def move_project(project_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    """Déplace un projet vers une autre colonne Kanban."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Projet introuvable")
    project.kanban_column_id = data["kanban_column_id"]
    if "status" in data:
        project.status = data["status"]
    await db.flush()
    await db.refresh(project)
    return _project_to_dict(project)


def _project_to_dict(p: Project) -> dict:
    from datetime import date
    days_waiting = None
    if p.waiting_since and p.status == "waiting_third_party":
        days_waiting = (date.today() - p.waiting_since).days
    return {
        "id": str(p.id),
        "client_id": str(p.client_id) if p.client_id else None,
        "contract_id": str(p.contract_id) if p.contract_id else None,
        "title": p.title,
        "description": p.description,
        "status": p.status,
        "priority": p.priority,
        "kanban_column_id": str(p.kanban_column_id) if p.kanban_column_id else None,
        "waiting_for": p.waiting_for,
        "waiting_since": p.waiting_since.isoformat() if p.waiting_since else None,
        "days_waiting": days_waiting,
        "auto_remind_days": p.auto_remind_days,
        "needs_reminder": days_waiting >= p.auto_remind_days if days_waiting is not None else False,
        "due_date": p.due_date.isoformat() if p.due_date else None,
        "estimated_hours": float(p.estimated_hours) if p.estimated_hours else None,
        "tags": p.tags,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }

HEREDOC

cat > /srv/smarthub/api/app/routers/equipment.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
from datetime import date

from ..core.database import get_db
from ..models.equipment import Equipment, WorkshopIntervention, EquipmentType, EquipmentStatus

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("/", response_model=list[dict])
async def list_equipment(
    client_id: Optional[UUID] = None,
    status: Optional[EquipmentStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(Equipment)
    if client_id:
        query = query.where(Equipment.client_id == client_id)
    if status:
        query = query.where(Equipment.status == status)
    query = query.order_by(Equipment.created_at.desc())
    result = await db.execute(query)
    return [_eq_to_dict(e) for e in result.scalars().all()]


@router.get("/{equipment_id}", response_model=dict)
async def get_equipment(equipment_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    return _eq_to_dict(eq)


@router.post("/", response_model=dict, status_code=201)
async def create_equipment(data: dict, db: AsyncSession = Depends(get_db)):
    eq = Equipment(**data)
    db.add(eq)
    await db.flush()
    await db.refresh(eq)
    return _eq_to_dict(eq)


@router.patch("/{equipment_id}", response_model=dict)
async def update_equipment(equipment_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Equipment).where(Equipment.id == equipment_id))
    eq = result.scalar_one_or_none()
    if not eq:
        raise HTTPException(status_code=404, detail="Équipement introuvable")
    for key, value in data.items():
        if hasattr(eq, key):
            setattr(eq, key, value)
    await db.flush()
    await db.refresh(eq)
    return _eq_to_dict(eq)


# ── Interventions atelier ──────────────────────────────────

@router.get("/{equipment_id}/interventions", response_model=list[dict])
async def list_interventions(equipment_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WorkshopIntervention)
        .where(WorkshopIntervention.equipment_id == equipment_id)
        .order_by(WorkshopIntervention.intervention_date.desc())
    )
    return [_intervention_to_dict(i) for i in result.scalars().all()]


@router.post("/{equipment_id}/interventions", response_model=dict, status_code=201)
async def create_intervention(equipment_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    data["equipment_id"] = str(equipment_id)
    if "intervention_date" not in data:
        data["intervention_date"] = date.today().isoformat()
    intervention = WorkshopIntervention(**data)
    db.add(intervention)
    await db.flush()
    await db.refresh(intervention)
    return _intervention_to_dict(intervention)


def _eq_to_dict(e: Equipment) -> dict:
    return {
        "id": str(e.id),
        "client_id": str(e.client_id),
        "site_id": str(e.site_id) if e.site_id else None,
        "serial_number": e.serial_number,
        "asset_tag": e.asset_tag,
        "type": e.type,
        "brand": e.brand,
        "model": e.model,
        "specs_json": e.specs_json,
        "purchase_date": e.purchase_date.isoformat() if e.purchase_date else None,
        "warranty_until": e.warranty_until.isoformat() if e.warranty_until else None,
        "status": e.status,
        "nas_path": e.nas_path,
        "notes": e.notes,
        "created_at": e.created_at.isoformat(),
    }


def _intervention_to_dict(i: WorkshopIntervention) -> dict:
    return {
        "id": str(i.id),
        "equipment_id": str(i.equipment_id),
        "contract_id": str(i.contract_id) if i.contract_id else None,
        "intervention_type": i.intervention_type,
        "intervention_date": i.intervention_date.isoformat(),
        "technician": i.technician,
        "summary": i.summary,
        "checks_json": i.checks_json,
        "hdshredder_report_path": i.hdshredder_report_path,
        "pdf_report_path": i.pdf_report_path,
        "is_billable": i.is_billable,
        "billed_amount": float(i.billed_amount) if i.billed_amount else None,
        "created_at": i.created_at.isoformat(),
    }

HEREDOC

cat > /srv/smarthub/api/app/routers/forensics.py << 'HEREDOC'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional
from datetime import datetime, timezone

from ..core.database import get_db
from ..models.forensics import ForensicsCase, ForensicsEvidence, ForensicsStatus
from ..models.contract import Contract, ContractType, ContractStatus

router = APIRouter(prefix="/forensics", tags=["forensics"])


@router.get("/", response_model=list[dict])
async def list_cases(
    client_id: Optional[UUID] = None,
    status: Optional[ForensicsStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(ForensicsCase).order_by(ForensicsCase.opened_at.desc())
    if client_id:
        query = query.where(ForensicsCase.client_id == client_id)
    if status:
        query = query.where(ForensicsCase.status == status)
    result = await db.execute(query)
    return [_case_to_dict(c) for c in result.scalars().all()]


@router.get("/{case_id}", response_model=dict)
async def get_case(case_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ForensicsCase).where(ForensicsCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    evidence = await db.execute(
        select(ForensicsEvidence).where(ForensicsEvidence.case_id == case_id)
        .order_by(ForensicsEvidence.evidence_number)
    )
    d = _case_to_dict(case)
    d["evidence"] = [_evidence_to_dict(e) for e in evidence.scalars().all()]
    return d


@router.post("/", response_model=dict, status_code=201)
async def create_case(data: dict, db: AsyncSession = Depends(get_db)):
    """Création d'un dossier forensics — vérifie que la LM est signée."""
    contract_id = data.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="Une lettre de mission signée est obligatoire")

    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    if contract.contract_type != ContractType.lm_forensics:
        raise HTTPException(status_code=400, detail=f"Le contrat doit être de type lm_forensics (reçu: {contract.contract_type})")
    if contract.status not in [ContractStatus.signé, ContractStatus.actif]:
        raise HTTPException(status_code=400, detail=f"La LM doit être signée (statut actuel: {contract.status})")

    # Génération référence
    if "case_reference" not in data or not data["case_reference"]:
        from datetime import date
        year = date.today().year
        count = await db.execute(select(ForensicsCase).where(ForensicsCase.client_id == data["client_id"]))
        seq = len(count.scalars().all()) + 1
        data["case_reference"] = f"FOR-{year}-{str(seq).zfill(3)}"

    case = ForensicsCase(**data)
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return _case_to_dict(case)


@router.patch("/{case_id}", response_model=dict)
async def update_case(case_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ForensicsCase).where(ForensicsCase.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Dossier introuvable")
    if "status" in data and data["status"] == "clôturé" and not case.closed_at:
        case.closed_at = datetime.now(timezone.utc)
    for key, value in data.items():
        if hasattr(case, key):
            setattr(case, key, value)
    await db.flush()
    await db.refresh(case)
    return _case_to_dict(case)


@router.post("/{case_id}/evidence", response_model=dict, status_code=201)
async def add_evidence(case_id: UUID, data: dict, db: AsyncSession = Depends(get_db)):
    data["case_id"] = str(case_id)
    if "acquisition_date" not in data:
        data["acquisition_date"] = datetime.now(timezone.utc).isoformat()
    evidence = ForensicsEvidence(**data)
    db.add(evidence)
    await db.flush()
    await db.refresh(evidence)
    return _evidence_to_dict(evidence)


def _case_to_dict(c: ForensicsCase) -> dict:
    return {
        "id": str(c.id),
        "client_id": str(c.client_id),
        "contract_id": str(c.contract_id),
        "case_reference": c.case_reference,
        "title": c.title,
        "objectives": c.objectives,
        "scope": c.scope,
        "status": c.status,
        "opened_at": c.opened_at.isoformat(),
        "closed_at": c.closed_at.isoformat() if c.closed_at else None,
        "final_report_path": c.final_report_path,
        "chain_of_custody_notes": c.chain_of_custody_notes,
        "created_at": c.created_at.isoformat(),
    }


def _evidence_to_dict(e: ForensicsEvidence) -> dict:
    return {
        "id": str(e.id),
        "case_id": str(e.case_id),
        "evidence_number": e.evidence_number,
        "description": e.description,
        "type": e.type,
        "serial_number": e.serial_number,
        "hash_md5": e.hash_md5,
        "hash_sha256": e.hash_sha256,
        "acquisition_date": e.acquisition_date.isoformat(),
        "acquisition_tool": e.acquisition_tool,
        "storage_location": e.storage_location,
        "nas_path": e.nas_path,
    }

HEREDOC

cat > /srv/smarthub/api/app/routers/dashboard.py << 'HEREDOC'
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_model=dict)
async def dashboard(db: AsyncSession = Depends(get_db)):
    """Vue d'ensemble — données pour le dashboard principal."""

    # Stats du jour
    today = await db.execute(text("""
        SELECT
            COUNT(*)                                                    AS sessions_today,
            COALESCE(SUM(duration_minutes), 0)                         AS minutes_today,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_today,
            COUNT(CASE WHEN ended_at IS NULL THEN 1 END)               AS active_sessions
        FROM time_sessions
        WHERE started_at::date = CURRENT_DATE
    """))
    today_row = today.mappings().first()

    # Stats du mois
    month = await db.execute(text("""
        SELECT
            COALESCE(SUM(duration_minutes), 0)                         AS minutes_month,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_month
        FROM time_sessions
        WHERE date_trunc('month', started_at) = date_trunc('month', CURRENT_DATE)
    """))
    month_row = month.mappings().first()

    # Contrats actifs
    contracts = await db.execute(text("""
        SELECT COUNT(*) AS active_contracts
        FROM contracts WHERE status = 'actif'
    """))
    contracts_row = contracts.mappings().first()

    # Alertes renouvellement
    renewals = await db.execute(text("""
        SELECT COUNT(*) AS renewal_count
        FROM v_contracts_renewal
    """))
    renewals_row = renewals.mappings().first()

    # Projets en attente tiers
    waiting = await db.execute(text("""
        SELECT COUNT(*) AS waiting_count,
               COUNT(CASE WHEN needs_reminder THEN 1 END) AS needs_reminder_count
        FROM v_projects_waiting
    """))
    waiting_row = waiting.mappings().first()

    # Clients actifs
    clients = await db.execute(text("""
        SELECT COUNT(*) AS active_clients FROM clients WHERE status = 'actif'
    """))
    clients_row = clients.mappings().first()

    # Sessions récentes
    recent = await db.execute(text("""
        SELECT ts.id, cl.name AS client_name, ts.activity,
               ts.started_at, ts.ended_at, ts.duration_minutes, ts.amount
        FROM time_sessions ts
        JOIN clients cl ON cl.id = ts.client_id
        ORDER BY ts.started_at DESC
        LIMIT 8
    """))
    recent_sessions = [dict(r) for r in recent.mappings().all()]

    return {
        "today": {
            "sessions": today_row["sessions_today"],
            "hours": round(float(today_row["minutes_today"] or 0) / 60, 2),
            "billable": float(today_row["billable_today"] or 0),
            "active_sessions": today_row["active_sessions"],
        },
        "month": {
            "hours": round(float(month_row["minutes_month"] or 0) / 60, 2),
            "billable": float(month_row["billable_month"] or 0),
        },
        "alerts": {
            "active_contracts": contracts_row["active_contracts"],
            "renewal_alerts": renewals_row["renewal_count"],
            "projects_waiting": waiting_row["waiting_count"],
            "projects_need_reminder": waiting_row["needs_reminder_count"],
            "active_clients": clients_row["active_clients"],
        },
        "recent_sessions": recent_sessions,
    }

HEREDOC

cat > /srv/smarthub/api/app/routers/__init__.py << 'HEREDOC'
from . import clients, timetrack, contracts, projects, equipment, forensics, dashboard

HEREDOC


# Mise à jour main.py
cat > /srv/smarthub/api/app/main.py << 'HEREDOC'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import get_settings
from .routers import clients, timetrack, contracts, projects, equipment, forensics, dashboard

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.app_name} v{settings.app_version} démarré")
    yield
    print("👋 Arrêt propre")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="API backend du Smarthub — ERP Smartclick BV",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clients.router, prefix="/api/v1")
app.include_router(timetrack.router, prefix="/api/v1")
app.include_router(contracts.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(equipment.router, prefix="/api/v1")
app.include_router(forensics.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root():
    return {"message": "Smarthub API", "docs": "/docs"}
HEREDOC

echo '✅ Routers créés!'
echo '🔄 Redémarrage API...'
cd /srv/smarthub && docker compose restart api
sleep 4
docker logs smarthub-api --tail=8
