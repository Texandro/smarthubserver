from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import Optional
from datetime import date

from ..core.database import get_db
from ..models.contract import Contract, ContractItem, ContractType, ContractStatus
from ..models.client import Client
from ..models.auth import User
from ..auth import get_current_user, require_owner


router = APIRouter(prefix="/contracts", tags=["contracts"])


def _contract_dict(c: Contract) -> dict:
    return {
        "id":                   str(c.id),
        "client_id":            str(c.client_id),
        "client_name":          getattr(c, "_client_name", ""),
        "site_id":              str(c.site_id) if c.site_id else None,
        "contract_type":        c.contract_type,
        "reference":            c.reference,
        "title":                c.title,
        "status":               c.status,
        "billing_type":         c.billing_type,
        "start_date":           c.start_date.isoformat() if c.start_date else None,
        "end_date":             c.end_date.isoformat() if c.end_date else None,
        "renewal_reminder_days":c.renewal_reminder_days,
        "sold_hours":           float(c.sold_hours) if c.sold_hours else None,
        "sold_budget":          float(c.sold_budget) if c.sold_budget else None,
        "hourly_rate":          float(c.hourly_rate) if c.hourly_rate else None,
        "monthly_amount":       float(c.monthly_amount) if c.monthly_amount else None,
        "signed_at":            c.signed_at.isoformat() if c.signed_at else None,
        "signed_by_name":       c.signed_by_name,
        "notes":                c.notes,
        "created_at":           c.created_at.isoformat(),
        "items": [
            {
                "id":          str(i.id),
                "description": i.description,
                "unit_price":  float(i.unit_price) if i.unit_price else None,
                "quantity":    float(i.quantity),
                "unit":        i.unit,
                "is_included": i.is_included,
                "position":    i.position,
            }
            for i in (c.items or [])
        ],
    }


def _generate_reference(contract_type: str, client_name: str, year: int, seq: int) -> str:
    prefixes = {
        "maintenance":      "CM",
        "lm_forensics":     "LM-FOR",
        "lm_datashredding": "LM-DS",
        "lm_dev":           "DEV",
        "lm_it_management": "LM-IT",
        "devis":            "DEV",
        "autre":            "CTR",
    }
    prefix = prefixes.get(contract_type, "CTR")
    slug   = "".join(c for c in client_name.upper()[:3] if c.isalpha())
    return f"{prefix}-{slug}-{year}-{str(seq).zfill(3)}"


@router.get("/", response_model=list[dict])
async def list_contracts(
    client_id : Optional[UUID] = None,
    status    : Optional[str]  = None,
    db        : AsyncSession   = Depends(get_db),
    _         : User           = Depends(require_owner),
):
    query = (
        select(Contract)
        .options(selectinload(Contract.items))
        .order_by(Contract.created_at.desc())
    )
    if client_id:
        query = query.where(Contract.client_id == client_id)
    if status:
        query = query.where(Contract.status == status)
    result = await db.execute(query)
    contracts = result.scalars().all()
    # Injecter client_name via requête SQL
    for c in contracts:
        cr = await db.execute(select(Client.name).where(Client.id == c.client_id))
        c._client_name = cr.scalar_one_or_none() or ""
    return [_contract_dict(c) for c in contracts]


@router.get("/renewal-alerts", response_model=list[dict])
async def renewal_alerts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(text("""
        SELECT id, reference, title, end_date,
               end_date - CURRENT_DATE AS days_until_expiry,
               client_id, renewal_reminder_days
        FROM contracts
        WHERE end_date IS NOT NULL AND status = 'actif'
          AND end_date - CURRENT_DATE <= renewal_reminder_days
        ORDER BY days_until_expiry ASC
    """))
    return [dict(r) for r in result.mappings().all()]


@router.get("/profitability", response_model=list[dict])
async def profitability(
    client_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    q = "SELECT * FROM v_contract_profitability WHERE 1=1"
    params = {}
    if client_id:
        q += " AND client_id = :cid"
        params["cid"] = str(client_id)
    q += " ORDER BY start_date DESC"
    result = await db.execute(text(q), params)
    return [dict(r) for r in result.mappings().all()]


@router.get("/{contract_id}", response_model=dict)
async def get_contract(
    contract_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items))
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    cr = await db.execute(select(Client.name).where(Client.id == contract.client_id))
    contract._client_name = cr.scalar_one_or_none() or ""
    return _contract_dict(contract)


@router.post("/", response_model=dict, status_code=201)
async def create_contract(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    items_data = data.pop("items", [])
    for field in ["id", "created_at", "updated_at"]:
        data.pop(field, None)

    # Génération référence auto
    if not data.get("reference"):
        result = await db.execute(select(Client).where(Client.id == data["client_id"]))
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=404, detail="Client introuvable")
        year = date.today().year
        # Compter uniquement les contrats du même type pour ce client cette année
        from sqlalchemy import func, extract
        count_r = await db.execute(
            select(func.count(Contract.id)).where(
                Contract.client_id    == data["client_id"],
                Contract.contract_type == data["contract_type"],
                extract("year", Contract.created_at) == year,
            )
        )
        seq = (count_r.scalar() or 0) + 1
        data["reference"] = _generate_reference(
            data["contract_type"], client.name, year, seq
        )
        client_name = client.name
    else:
        cr = await db.execute(select(Client.name).where(Client.id == data["client_id"]))
        client_name = cr.scalar_one_or_none() or ""

    # Convertir les dates string → objet date Python
    from datetime import date as _date
    for df in ["start_date", "end_date", "signed_at"]:
        if data.get(df) and isinstance(data[df], str) and data[df]:
            try:
                data[df] = _date.fromisoformat(data[df][:10])
            except ValueError:
                data.pop(df, None)
    contract = Contract(**data)
    db.add(contract)
    await db.flush()

    for item in items_data:
        item.pop("id", None)
        db.add(ContractItem(contract_id=contract.id, **item))

    await db.flush()
    result2 = await db.execute(
        select(Contract).options(selectinload(Contract.items))
        .where(Contract.id == contract.id)
    )
    contract = result2.scalar_one()
    contract._client_name = client_name
    return _contract_dict(contract)


@router.patch("/{contract_id}", response_model=dict)
async def update_contract(
    contract_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    result = await db.execute(
        select(Contract).options(selectinload(Contract.items))
        .where(Contract.id == contract_id)
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(status_code=404, detail="Contrat introuvable")
    for field in ["id", "created_at", "updated_at", "items", "client_name", "reference"]:
        data.pop(field, None)

    # Parser les dates string → date object
    from datetime import date as _date
    import uuid as _uuid
    for df in ["start_date", "end_date", "signed_at"]:
        val = data.get(df)
        if isinstance(val, str) and val:
            try:
                data[df] = _date.fromisoformat(val[:10])
            except ValueError:
                data.pop(df, None)
        elif val is None:
            data.pop(df, None)

    # Parser client_id string → uuid.UUID
    for uf in ["client_id"]:
        val = data.get(uf)
        if isinstance(val, str) and val:
            try:
                data[uf] = _uuid.UUID(val)
            except ValueError:
                data.pop(uf, None)

    for key, value in data.items():
        if hasattr(contract, key):
            setattr(contract, key, value)
    await db.flush()
    await db.refresh(contract)
    cr = await db.execute(select(Client.name).where(Client.id == contract.client_id))
    contract._client_name = cr.scalar_one_or_none() or ""
    return _contract_dict(contract)
