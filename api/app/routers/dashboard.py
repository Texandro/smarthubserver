from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..core.database import get_db
from ..models.auth import User, UserRole
from ..auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/", response_model=dict)
async def dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dashboard principal.
    Owner : vue complète (sessions, contrats, projets, alertes).
    Technicien : vue réduite (ses sessions du jour, ses interventions).
    """
    # Stats du jour — communes
    today = await db.execute(text("""
        SELECT
            COUNT(*)                                                        AS sessions_today,
            COALESCE(SUM(duration_minutes), 0)                             AS minutes_today,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_today,
            COUNT(CASE WHEN ended_at IS NULL THEN 1 END)                   AS active_sessions
        FROM time_sessions
        WHERE started_at::date = CURRENT_DATE
    """))
    tr = today.mappings().first()

    # Stats du mois
    month = await db.execute(text("""
        SELECT
            COALESCE(SUM(duration_minutes), 0)                             AS minutes_month,
            COALESCE(SUM(CASE WHEN is_billable THEN amount ELSE 0 END), 0) AS billable_month
        FROM time_sessions
        WHERE date_trunc('month', started_at) = date_trunc('month', CURRENT_DATE)
    """))
    mr = month.mappings().first()

    # Sessions récentes
    recent = await db.execute(text("""
        SELECT ts.id, cl.name AS client_name, ts.activity,
               ts.started_at, ts.ended_at, ts.duration_minutes,
               ts.is_billable, ts.amount
        FROM time_sessions ts
        JOIN clients cl ON cl.id = ts.client_id
        ORDER BY ts.started_at DESC LIMIT 8
    """))
    recent_sessions = [dict(r) for r in recent.mappings().all()]

    base = {
        "user": {
            "name":  current_user.name,
            "role":  current_user.role,
            "email": current_user.email,
        },
        "today": {
            "sessions":        int(tr["sessions_today"]),
            "hours":           round(float(tr["minutes_today"] or 0) / 60, 2),
            "billable":        float(tr["billable_today"] or 0),
            "active_sessions": int(tr["active_sessions"]),
        },
        "month": {
            "hours":    round(float(mr["minutes_month"] or 0) / 60, 2),
            "billable": float(mr["billable_month"] or 0),
        },
        "recent_sessions": recent_sessions,
    }

    # Données supplémentaires owner uniquement
    if current_user.role == UserRole.owner:
        contracts = await db.execute(text(
            "SELECT COUNT(*) AS n FROM contracts WHERE status = 'actif'"
        ))
        renewals = await db.execute(text(
            "SELECT COUNT(*) AS n FROM v_contracts_renewal"
        ))
        waiting = await db.execute(text(
            "SELECT COUNT(*) AS n, COUNT(CASE WHEN needs_reminder THEN 1 END) AS remind FROM v_projects_waiting"
        ))
        clients = await db.execute(text(
            "SELECT COUNT(*) AS n FROM clients WHERE status = 'actif'"
        ))
        wr = waiting.mappings().first()
        base["alerts"] = {
            "active_contracts":     int(contracts.mappings().first()["n"]),
            "renewal_alerts":       int(renewals.mappings().first()["n"]),
            "projects_waiting":     int(wr["n"]),
            "projects_need_remind": int(wr["remind"]),
            "active_clients":       int(clients.mappings().first()["n"]),
        }

    return base
