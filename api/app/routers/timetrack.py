"""
SmartHub — Router Timetrack
Toutes les sessions de temps, toutes sources consolidées.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, cast
from sqlalchemy.dialects.postgresql import TIMESTAMP as PG_TIMESTAMP
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone, date
from typing import Optional

from ..core.database import get_db
from ..models.timetrack import TimeSession, SessionReport
from ..models.client import Client
from ..models.auth import User
from ..auth import get_current_user

router = APIRouter(prefix="/timetrack", tags=["timetrack"])


def _session_dict(s: TimeSession, client_name: str = "", contract_ref: str = "") -> dict:
    # Calculer duration_minutes et amount en Python (colonnes GENERATED ALWAYS AS non chargées par l'ORM)
    if s.ended_at and s.started_at:
        started = s.started_at if s.started_at.tzinfo else s.started_at.replace(tzinfo=timezone.utc)
        ended   = s.ended_at   if s.ended_at.tzinfo   else s.ended_at.replace(tzinfo=timezone.utc)
        elapsed_seconds  = (ended - started).total_seconds()
        duration_minutes = int(elapsed_seconds / 60)
        amount = (
            round((elapsed_seconds / 3600) * float(s.hourly_rate_applied), 2)
            if s.hourly_rate_applied else None
        )
    else:
        duration_minutes = None
        amount           = None

    return {
        "id":                       str(s.id),
        "client_id":                str(s.client_id),
        "client_name":              client_name,
        "site_id":                  str(s.site_id) if s.site_id else None,
        "contract_id":              str(s.contract_id) if s.contract_id else None,
        "project_id":               str(s.project_id) if s.project_id else None,
        "activity":                 s.activity,
        "description":              s.description,
        "started_at":               s.started_at.isoformat(),
        "ended_at":                 s.ended_at.isoformat() if s.ended_at else None,
        "duration_minutes":         duration_minutes,
        "amount":                   amount,
        "is_billable":              s.is_billable,
        "is_included_in_contract":  s.is_included_in_contract,
        "hourly_rate_applied":      float(s.hourly_rate_applied) if s.hourly_rate_applied else None,
        "tags":                     s.tags,
        "created_at":               s.created_at.isoformat(),
        "contract_ref":             contract_ref or None,
        "report": {
            "work_done":       s.report.work_done,
            "work_pending":    s.report.work_pending,
            "next_action":     s.report.next_action,
            "client_notified": s.report.client_notified,
        } if s.report else None,
    }


# ── Session active ─────────────────────────────────────────

@router.get("/active")
async def get_active_session(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Session en cours — pour la bannière workspace et l'overlay."""
    result = await db.execute(
        select(TimeSession, Client.name.label("cn"))
        .join(Client, TimeSession.client_id == Client.id)
        .where(TimeSession.ended_at.is_(None))
        .order_by(TimeSession.started_at.desc())
        .limit(1)
    )
    row = result.first()
    if not row:
        return None
    s, cn = row
    now = datetime.now(timezone.utc)
    started = s.started_at if s.started_at.tzinfo else s.started_at.replace(tzinfo=timezone.utc)
    live_minutes = int((now - started).total_seconds() / 60)
    return {
        "id":               str(s.id),
        "client_id":        str(s.client_id),
        "client_name":      cn,
        "activity":         s.activity,
        "started_at":       s.started_at.isoformat(),
        "duration_minutes": live_minutes,
        "is_billable":      s.is_billable,
        "contract_id":      str(s.contract_id) if s.contract_id else None,
        "project_id":       str(s.project_id) if s.project_id else None,
    }


# ── Start / Stop ───────────────────────────────────────────

@router.post("/start", response_model=dict, status_code=201)
async def start_session(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Démarre une session. Stoppe automatiquement toute session active.
    Body minimal: {"client_id": "...", "activity": "..."}
    Optionnel: contract_id, project_id, is_billable, hourly_rate_applied, tags, description
    """
    # Stopper les sessions actives
    active = await db.execute(select(TimeSession).where(TimeSession.ended_at.is_(None)))
    for s in active.scalars().all():
        s.ended_at = datetime.now(timezone.utc)

    # Mapper context_id → la bonne FK selon context_type avant de nettoyer
    context_type = data.pop("context_type", None)
    context_id   = data.pop("context_id",   None)
    if context_id:
        if context_type == "projet":
            data.setdefault("project_id",  context_id)
        elif context_type == "contrat":
            data.setdefault("contract_id", context_id)

    # Nettoyer TOUS les champs inconnus du modèle TimeSession
    ALLOWED = {
        "client_id", "site_id", "contract_id", "project_id",
        "activity", "description", "started_at",
        "is_billable", "is_included_in_contract",
        "hourly_rate_applied", "tags",
    }
    data = {k: v for k, v in data.items() if k in ALLOWED}

    data.setdefault("started_at", datetime.now(timezone.utc).isoformat())
    if isinstance(data["started_at"], str):
        data["started_at"] = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))

    # Taux horaire : contrat lié → sinon garder celui envoyé par Qt (taux par défaut config)
    if data.get("contract_id"):
        from ..models.contract import Contract as ContractModel
        cr = await db.execute(
            select(ContractModel.hourly_rate).where(ContractModel.id == data["contract_id"])
        )
        contract_rate = cr.scalar_one_or_none()
        if contract_rate:
            data["hourly_rate_applied"] = float(contract_rate)
        # Sinon on garde hourly_rate_applied envoyé par Qt (taux par défaut des Paramètres)

    session = TimeSession(**data)
    db.add(session)
    await db.flush()

    # Recharger avec selectinload pour éviter le lazy loading hors contexte async
    result2 = await db.execute(
        select(TimeSession, Client.name.label("cn"))
        .join(Client, TimeSession.client_id == Client.id)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.id == session.id)
    )
    row = result2.first()
    return _session_dict(row[0], row[1])


@router.post("/stop", response_model=dict)
async def stop_active_session(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    Stoppe la session active + enregistre le rapport.
    Body: {"notes": "...", "task_done": true}
    """
    result = await db.execute(
        select(TimeSession)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.ended_at.is_(None))
        .order_by(TimeSession.started_at.desc())
        .limit(1)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Aucune session active")

    session.ended_at = datetime.now(timezone.utc)

    notes = data.get("notes") or data.get("work_done")
    if notes:
        report = SessionReport(
            session_id   = session.id,
            work_done    = notes,
            work_pending = data.get("work_pending"),
            next_action  = data.get("next_action"),
        )
        db.add(report)


    await db.flush()
    await db.refresh(session)

    client = await db.execute(select(Client).where(Client.id == session.client_id))
    c = client.scalar_one_or_none()
    return _session_dict(session, c.name if c else "")


@router.post("/{session_id}/stop", response_model=dict)
async def stop_session_by_id(
    session_id: UUID,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stoppe une session par ID."""
    result = await db.execute(
        select(TimeSession)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")
    if session.ended_at:
        raise HTTPException(status_code=400, detail="Session déjà terminée")

    session.ended_at = data.get("ended_at") or datetime.now(timezone.utc)

    notes = data.get("notes") or data.get("work_done")
    if notes:
        report = SessionReport(
            session_id   = session.id,
            work_done    = notes,
            work_pending = data.get("work_pending"),
            next_action  = data.get("next_action"),
        )
        db.add(report)


    await db.flush()
    await db.refresh(session)

    client = await db.execute(select(Client).where(Client.id == session.client_id))
    c = client.scalar_one_or_none()
    return _session_dict(session, c.name if c else "")


# ── Liste sessions ─────────────────────────────────────────

@router.get("/", response_model=list[dict])
async def list_sessions(
    client_id   : Optional[UUID] = None,
    contract_id : Optional[UUID] = None,
    project_id  : Optional[UUID] = None,
    date_from   : Optional[str]  = None,
    date_to     : Optional[str]  = None,
    limit       : int            = 100,
    db          : AsyncSession   = Depends(get_db),
    _           : User           = Depends(get_current_user),
):
    from ..models.contract import Contract as ContractModel
    query = (
        select(TimeSession, Client.name.label("cn"),
               ContractModel.reference.label("cref"))
        .join(Client, TimeSession.client_id == Client.id)
        .outerjoin(ContractModel, TimeSession.contract_id == ContractModel.id)
        .options(selectinload(TimeSession.report))
        .order_by(TimeSession.started_at.desc())
        .limit(limit)
    )
    if client_id:
        query = query.where(TimeSession.client_id == client_id)
    if contract_id:
        query = query.where(TimeSession.contract_id == contract_id)
    if project_id:
        query = query.where(TimeSession.project_id == project_id)
    if date_from:
        from datetime import datetime
        _df = datetime.fromisoformat(date_from)
        query = query.where(TimeSession.started_at >= _df)
    if date_to:
        _dt = datetime.fromisoformat(date_to + "T23:59:59")
        query = query.where(TimeSession.started_at <= _dt)

    result = await db.execute(query)
    return [_session_dict(s, cn, cref or "") for s, cn, cref in result.all()]


@router.get("/{session_id}", response_model=dict)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TimeSession, Client.name.label("cn"))
        .join(Client, TimeSession.client_id == Client.id)
        .options(selectinload(TimeSession.report))
        .where(TimeSession.id == session_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return _session_dict(row[0], row[1])


# ── Stats ──────────────────────────────────────────────────

@router.get("/stats/today")
async def today_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(text("""
        SELECT
            COUNT(*)                                                        AS session_count,
            COALESCE(SUM(duration_minutes), 0)                             AS total_minutes,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_amount,
            COUNT(CASE WHEN ended_at IS NULL THEN 1 END)                   AS active_sessions
        FROM time_sessions
        WHERE started_at::date = CURRENT_DATE
    """))
    row = result.mappings().first()
    return {
        "session_count":   int(row["session_count"]),
        "total_hours":     round(float(row["total_minutes"] or 0) / 60, 2),
        "billable_amount": float(row["billable_amount"] or 0),
        "active_sessions": int(row["active_sessions"]),
    }


@router.get("/stats/finance")
async def finance_stats(
    date_from   : Optional[str]  = None,
    date_to     : Optional[str]  = None,
    client_id   : Optional[UUID] = None,
    db          : AsyncSession   = Depends(get_db),
    _           : User           = Depends(get_current_user),
):
    """Stats financières consolidées — alimente le module Finance du Qt."""
    filters = "WHERE 1=1"
    params  = {}
    if date_from:
        filters += " AND ts.started_at::date >= :df"
        params["df"] = date_from
    if date_to:
        filters += " AND ts.started_at::date <= :dt"
        params["dt"] = date_to
    if client_id:
        filters += " AND ts.client_id = :cid"
        params["cid"] = str(client_id)

    result = await db.execute(text(f"""
        SELECT
            cl.name                                                         AS client_name,
            ts.activity,
            ts.started_at::date                                             AS date,
            ts.duration_minutes,
            ts.is_billable,
            ts.is_included_in_contract,
            ts.amount,
            ts.hourly_rate_applied,
            c.reference                                                     AS contract_ref
        FROM time_sessions ts
        JOIN clients cl ON cl.id = ts.client_id
        LEFT JOIN contracts c ON c.id = ts.contract_id
        {filters}
        ORDER BY ts.started_at DESC
    """), params)
    return [dict(r) for r in result.mappings().all()]
