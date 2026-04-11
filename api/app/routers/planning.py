"""
SmartHub — Router Planning
Créneaux prévisionnels avec récurrences expansées à la volée.
Cf. PLANNING_BACKEND_SPEC.md à la racine du repo.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timezone, date, timedelta
from typing import Optional
from calendar import monthrange

from ..core.database import get_db
from ..models.planning import PlanningSlot, RecurrenceRule
from ..models.client import Client
from ..models.project import Project
from ..models.timetrack import TimeSession
from ..models.auth import User
from ..auth import get_current_user
import uuid as _uuid_mod

router = APIRouter(prefix="/planning", tags=["planning"])


# ── Helpers ────────────────────────────────────────────────

OVERRUN_RATIO = 1.15  # >115% du prévu => overrun


def _to_uuid(val) -> Optional[UUID]:
    """Convertit string → UUID, retourne None si invalide ou vide."""
    if val is None:
        return None
    if isinstance(val, _uuid_mod.UUID):
        return val
    try:
        return _uuid_mod.UUID(str(val))
    except (ValueError, AttributeError):
        return None


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _compute_status(slot: PlanningSlot, now: Optional[datetime] = None) -> str:
    """Cf. spec section 4."""
    now = now or datetime.now(timezone.utc)
    # Déjà terminé en BDD ou session liée
    if slot.actual_session_id is not None or slot.status in ("done", "overrun"):
        if slot.actual_duration_min and slot.actual_duration_min > slot.duration_min * OVERRUN_RATIO:
            return "overrun"
        return "done"
    if slot.status == "in_progress":
        return "in_progress"
    start = _aware(slot.start_at)
    end   = start + timedelta(minutes=slot.duration_min)
    if now < start:
        return "planned"
    if start <= now <= end:
        # Pas démarré explicitement mais on est dans la fenêtre :
        # on reste en "planned" (l'utilisateur ne l'a pas lancé), pas "in_progress"
        return "planned"
    return "missed"


def _slot_dict(
    slot: PlanningSlot,
    *,
    client_name: Optional[str] = None,
    dossier_title: Optional[str] = None,
    start_at_override: Optional[datetime] = None,
    is_occurrence: bool = False,
    occurrence_of: Optional[UUID] = None,
    now: Optional[datetime] = None,
) -> dict:
    start_at = start_at_override or _aware(slot.start_at)
    # Pour le calcul de status sur une occurrence virtuelle, on simule un slot
    # avec le start_at de l'occurrence
    if is_occurrence:
        # Une occurrence virtuelle n'a jamais de session liée — son statut dépend
        # juste de sa position temporelle
        now = now or datetime.now(timezone.utc)
        end = start_at + timedelta(minutes=slot.duration_min)
        if now < start_at:
            status = "planned"
        elif now <= end:
            status = "planned"
        else:
            status = "missed"
    else:
        status = _compute_status(slot, now=now)

    return {
        "id":                   str(slot.id),
        "title":                slot.title,
        "client_id":            str(slot.client_id) if slot.client_id else None,
        "client_name":          client_name,
        "dossier_id":           str(slot.dossier_id) if slot.dossier_id else None,
        "dossier_title":        dossier_title,
        "context_type":         slot.context_type,
        "context_id":           str(slot.context_id) if slot.context_id else None,
        "context_ref":          slot.context_ref,
        "start_at":             start_at.isoformat(),
        "duration_min":         slot.duration_min,
        "status":               status,
        "notes":                slot.notes,
        "recurrence_rule":      slot.recurrence_rule.rrule if slot.recurrence_rule else None,
        "recurrence_parent_id": str(slot.recurrence_parent_id) if slot.recurrence_parent_id else None,
        "actual_session_id":    str(slot.actual_session_id) if slot.actual_session_id else None,
        "actual_duration_min":  slot.actual_duration_min,
        "gcal_event_id":        slot.gcal_event_id,
        "_is_occurrence":       is_occurrence,
        "_occurrence_of":       str(occurrence_of) if occurrence_of else None,
        "created_at":           _aware(slot.created_at).isoformat() if slot.created_at else None,
        "updated_at":           _aware(slot.updated_at).isoformat() if slot.updated_at else None,
    }


def _iter_recurrence(
    base_start: datetime,
    rrule: str,
    until: Optional[date],
    window_from: date,
    window_to: date,
):
    """Itère sur les occurrences d'une règle dans la fenêtre [window_from, window_to].
    Retourne des datetime aware (mêmes h/m/s/tz que base_start)."""
    base_start = _aware(base_start)
    if rrule == "daily":
        step = timedelta(days=1)
    elif rrule == "weekly":
        step = timedelta(weeks=1)
    elif rrule == "monthly":
        step = None  # géré à la main
    else:
        return  # rrule inconnue → ne génère rien

    # Limite haute : la fin de la fenêtre, bornée par until_date
    hard_stop = window_to
    if until and until < hard_stop:
        hard_stop = until

    # Évite les boucles pathologiques (max 5 ans)
    safety_limit = 5 * 366

    current = base_start
    count = 0
    while current.date() <= hard_stop and count < safety_limit:
        if current.date() >= window_from:
            yield current
        # Avancer
        if rrule == "monthly":
            # Garde le même jour du mois si possible
            year  = current.year + (1 if current.month == 12 else 0)
            month = 1 if current.month == 12 else current.month + 1
            day   = min(base_start.day, monthrange(year, month)[1])
            current = current.replace(year=year, month=month, day=day)
        else:
            current = current + step
        count += 1


async def _client_name(db: AsyncSession, cid: Optional[UUID]) -> Optional[str]:
    if not cid:
        return None
    r = await db.execute(select(Client.name).where(Client.id == cid))
    return r.scalar_one_or_none()


async def _dossier_title(db: AsyncSession, did: Optional[UUID]) -> Optional[str]:
    if not did:
        return None
    r = await db.execute(select(Project.title).where(Project.id == did))
    return r.scalar_one_or_none()


# ── GET /planning/expanded ─────────────────────────────────

@router.get("/expanded", response_model=list[dict])
async def get_expanded(
    date_from   : str           = Query(..., description="YYYY-MM-DD"),
    date_to     : str           = Query(..., description="YYYY-MM-DD"),
    client_id   : Optional[UUID]= None,
    dossier_id  : Optional[UUID]= None,
    db          : AsyncSession  = Depends(get_db),
    _           : User          = Depends(get_current_user),
):
    """Endpoint principal de la vue jour/semaine. Récurrences expansées côté serveur."""
    try:
        df = date.fromisoformat(date_from)
        dt = date.fromisoformat(date_to)
    except ValueError:
        raise HTTPException(status_code=400, detail="date_from/date_to attendus en YYYY-MM-DD")
    if dt < df:
        raise HTTPException(status_code=400, detail="date_to doit être >= date_from")

    # Récupère tous les slots concernés (filtres optionnels)
    query = (
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .order_by(PlanningSlot.start_at.asc())
    )
    if client_id:
        query = query.where(PlanningSlot.client_id == client_id)
    if dossier_id:
        query = query.where(PlanningSlot.dossier_id == dossier_id)

    result = await db.execute(query)
    slots: list[PlanningSlot] = list(result.scalars().all())

    # Pré-fetch noms (1 query par client/dossier distinct)
    client_ids   = {s.client_id  for s in slots if s.client_id}
    dossier_ids  = {s.dossier_id for s in slots if s.dossier_id}

    client_names: dict[UUID, str] = {}
    if client_ids:
        r = await db.execute(select(Client.id, Client.name).where(Client.id.in_(client_ids)))
        client_names = {row[0]: row[1] for row in r.all()}
    dossier_titles: dict[UUID, str] = {}
    if dossier_ids:
        r = await db.execute(select(Project.id, Project.title).where(Project.id.in_(dossier_ids)))
        dossier_titles = {row[0]: row[1] for row in r.all()}

    # Index des enfants (exceptions) pour ne pas dupliquer les occurrences remplacées
    children_by_parent: dict[UUID, list[PlanningSlot]] = {}
    for s in slots:
        if s.recurrence_parent_id:
            children_by_parent.setdefault(s.recurrence_parent_id, []).append(s)

    now = datetime.now(timezone.utc)
    result_list: list[dict] = []

    for slot in slots:
        cn = client_names.get(slot.client_id)
        dt_title = dossier_titles.get(slot.dossier_id) if slot.dossier_id else None

        if slot.recurrence_rule_id is None:
            # Slot ponctuel : inclure s'il tombe dans la fenêtre
            sd = _aware(slot.start_at).date()
            if df <= sd <= dt:
                result_list.append(_slot_dict(
                    slot, client_name=cn, dossier_title=dt_title, now=now,
                ))
            continue

        # Slot série récurrente
        rule = slot.recurrence_rule
        if rule is None:
            continue
        exceptions_set = set(rule.exceptions or [])

        # Dates des occurrences déplacées (= enfants)
        replaced_dates = set()
        for child in children_by_parent.get(slot.id, []):
            # On considère qu'un child remplace l'occurrence du jour de son start_at d'origine ;
            # la spec stocke ces dates dans rule.exceptions ; on s'assure d'au moins éviter
            # le doublon visuel sur la nouvelle date du child aussi.
            replaced_dates.add(_aware(child.start_at).date().isoformat())

        for occ_dt in _iter_recurrence(slot.start_at, rule.rrule, rule.until_date, df, dt):
            occ_iso = occ_dt.date().isoformat()
            if occ_iso in exceptions_set:
                continue
            result_list.append(_slot_dict(
                slot,
                client_name=cn,
                dossier_title=dt_title,
                start_at_override=occ_dt,
                is_occurrence=True,
                occurrence_of=slot.id,
                now=now,
            ))

    result_list.sort(key=lambda d: d["start_at"])
    return result_list


# ── GET /planning/{id} ─────────────────────────────────────

@router.get("/{slot_id}", response_model=dict)
async def get_slot(
    slot_id : UUID,
    db      : AsyncSession = Depends(get_db),
    _       : User         = Depends(get_current_user),
):
    r = await db.execute(
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .where(PlanningSlot.id == slot_id)
    )
    slot = r.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")

    cn = await _client_name(db, slot.client_id)
    dt = await _dossier_title(db, slot.dossier_id)
    out = _slot_dict(slot, client_name=cn, dossier_title=dt)

    # Optionnel : payload session timetrack si liée
    if slot.actual_session_id:
        sr = await db.execute(select(TimeSession).where(TimeSession.id == slot.actual_session_id))
        s = sr.scalar_one_or_none()
        if s:
            out["actual_session"] = {
                "id":               str(s.id),
                "started_at":       _aware(s.started_at).isoformat(),
                "ended_at":         _aware(s.ended_at).isoformat() if s.ended_at else None,
                "activity":         s.activity,
                "client_id":        str(s.client_id),
                "is_billable":      s.is_billable,
            }
    return out


# ── POST /planning/ ────────────────────────────────────────

@router.post("/", response_model=dict, status_code=201)
async def create_slot(
    data : dict,
    db   : AsyncSession = Depends(get_db),
    user : User         = Depends(get_current_user),
):
    """Crée un créneau (avec ou sans récurrence)."""
    title = (data.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title requis")

    start_at_raw = data.get("start_at")
    if not start_at_raw:
        raise HTTPException(status_code=400, detail="start_at requis")
    try:
        start_at = datetime.fromisoformat(str(start_at_raw).replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="start_at invalide (ISO 8601)")
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)

    duration_min = data.get("duration_min")
    if not isinstance(duration_min, int) or duration_min <= 0:
        raise HTTPException(status_code=400, detail="duration_min doit être un entier > 0")

    # Récurrence éventuelle
    rrule_value = (data.get("recurrence_rule") or "").strip()
    rule_id: Optional[int] = None
    if rrule_value:
        if rrule_value not in ("daily", "weekly", "monthly"):
            raise HTTPException(status_code=400, detail="recurrence_rule doit être daily/weekly/monthly")
        until_raw = data.get("recurrence_until")
        until_date = None
        if until_raw:
            try:
                until_date = date.fromisoformat(str(until_raw))
            except ValueError:
                raise HTTPException(status_code=400, detail="recurrence_until invalide (YYYY-MM-DD)")
        rule = RecurrenceRule(rrule=rrule_value, until_date=until_date, exceptions=[])
        db.add(rule)
        await db.flush()
        rule_id = rule.id

    slot = PlanningSlot(
        title              = title,
        client_id          = _to_uuid(data.get("client_id")),
        dossier_id         = _to_uuid(data.get("dossier_id")),
        context_type       = data.get("context_type") or "manuel",
        context_id         = _to_uuid(data.get("context_id")),
        context_ref        = data.get("context_ref"),
        start_at           = start_at,
        duration_min       = duration_min,
        status             = "planned",
        notes              = data.get("notes"),
        recurrence_rule_id = rule_id,
        gcal_event_id      = data.get("gcal_event_id"),
        created_by         = user.id,
    )
    db.add(slot)
    await db.flush()
    await db.refresh(slot)

    # Recharger avec rule
    r = await db.execute(
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .where(PlanningSlot.id == slot.id)
    )
    slot = r.scalar_one()
    cn = await _client_name(db, slot.client_id)
    dt = await _dossier_title(db, slot.dossier_id)
    return _slot_dict(slot, client_name=cn, dossier_title=dt)


# ── PATCH /planning/{id} ───────────────────────────────────

@router.patch("/{slot_id}", response_model=dict)
async def update_slot(
    slot_id : UUID,
    data    : dict,
    db      : AsyncSession = Depends(get_db),
    user    : User         = Depends(get_current_user),
):
    r = await db.execute(
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .where(PlanningSlot.id == slot_id)
    )
    slot = r.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")

    # Cas spécial : modification d'une occurrence d'une série récurrente
    # → si l'utilisateur fournit `occurrence_date` (date de l'occurrence d'origine),
    #   on crée un slot enfant et on ajoute la date aux exceptions du parent.
    occurrence_date_raw = data.pop("occurrence_date", None)
    if slot.recurrence_rule_id is not None and occurrence_date_raw:
        try:
            occ_date = date.fromisoformat(str(occurrence_date_raw))
        except ValueError:
            raise HTTPException(status_code=400, detail="occurrence_date invalide (YYYY-MM-DD)")

        # Calcul du nouveau start_at (par défaut : mêmes h/m que la série, ou ce que le client envoie)
        new_start_raw = data.get("start_at")
        if new_start_raw:
            new_start = datetime.fromisoformat(str(new_start_raw).replace("Z", "+00:00"))
            if new_start.tzinfo is None:
                new_start = new_start.replace(tzinfo=timezone.utc)
        else:
            base = _aware(slot.start_at)
            new_start = base.replace(year=occ_date.year, month=occ_date.month, day=occ_date.day)

        child = PlanningSlot(
            title                = data.get("title")        or slot.title,
            client_id            = data.get("client_id")    or slot.client_id,
            dossier_id           = data.get("dossier_id")   or slot.dossier_id,
            context_type         = data.get("context_type") or slot.context_type,
            context_id           = data.get("context_id")   or slot.context_id,
            context_ref          = data.get("context_ref")  or slot.context_ref,
            start_at             = new_start,
            duration_min         = data.get("duration_min") or slot.duration_min,
            status               = "planned",
            notes                = data.get("notes")        if "notes" in data else slot.notes,
            recurrence_parent_id = slot.id,
            created_by           = user.id,
        )
        db.add(child)

        # Ajoute la date originale aux exceptions du parent
        rule = slot.recurrence_rule
        existing = list(rule.exceptions or [])
        if occ_date.isoformat() not in existing:
            existing.append(occ_date.isoformat())
            rule.exceptions = existing

        await db.flush()
        await db.refresh(child)
        cn = await _client_name(db, child.client_id)
        dt = await _dossier_title(db, child.dossier_id)
        return _slot_dict(child, client_name=cn, dossier_title=dt)

    # Modification standard
    SIMPLE_FIELDS = {"title", "client_id", "dossier_id", "context_type",
                     "context_id", "context_ref", "duration_min", "notes", "status",
                     "gcal_event_id"}
    for f in SIMPLE_FIELDS:
        if f in data:
            setattr(slot, f, data[f])

    if "start_at" in data and data["start_at"]:
        try:
            ns = datetime.fromisoformat(str(data["start_at"]).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="start_at invalide")
        if ns.tzinfo is None:
            ns = ns.replace(tzinfo=timezone.utc)
        slot.start_at = ns

    await db.flush()
    await db.refresh(slot)
    r = await db.execute(
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .where(PlanningSlot.id == slot.id)
    )
    slot = r.scalar_one()
    cn = await _client_name(db, slot.client_id)
    dtt = await _dossier_title(db, slot.dossier_id)
    return _slot_dict(slot, client_name=cn, dossier_title=dtt)


# ── DELETE /planning/{id} ──────────────────────────────────

@router.delete("/{slot_id}", status_code=204)
async def delete_slot(
    slot_id          : UUID,
    occurrence_date  : Optional[str]  = Query(None, description="YYYY-MM-DD pour ne supprimer qu'une occurrence"),
    db               : AsyncSession   = Depends(get_db),
    _                : User           = Depends(get_current_user),
):
    r = await db.execute(
        select(PlanningSlot)
        .options(selectinload(PlanningSlot.recurrence_rule))
        .where(PlanningSlot.id == slot_id)
    )
    slot = r.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")

    if occurrence_date and slot.recurrence_rule_id:
        try:
            occ = date.fromisoformat(occurrence_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="occurrence_date invalide")
        rule = slot.recurrence_rule
        existing = list(rule.exceptions or [])
        if occ.isoformat() not in existing:
            existing.append(occ.isoformat())
            rule.exceptions = existing
        await db.flush()
        return

    await db.delete(slot)
    await db.flush()
    return


# ── POST /planning/{id}/start ──────────────────────────────

@router.post("/{slot_id}/start", response_model=dict, status_code=201)
async def start_slot(
    slot_id : UUID,
    data    : Optional[dict] = None,
    db      : AsyncSession   = Depends(get_db),
    _       : User           = Depends(get_current_user),
):
    """Démarre une session timetrack liée au créneau."""
    data = data or {}
    r = await db.execute(select(PlanningSlot).where(PlanningSlot.id == slot_id))
    slot = r.scalar_one_or_none()
    if not slot:
        raise HTTPException(status_code=404, detail="Créneau introuvable")

    # 409 si une session est déjà active
    active = await db.execute(select(TimeSession).where(TimeSession.ended_at.is_(None)).limit(1))
    if active.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Une session timetrack est déjà active")

    if not slot.client_id:
        raise HTTPException(status_code=400, detail="Le créneau n'a pas de client — impossible de démarrer une session")

    session = TimeSession(
        client_id          = slot.client_id,
        project_id         = slot.dossier_id,
        planning_slot_id   = slot.id,
        activity           = data.get("activity") or slot.title,
        description        = data.get("description") or slot.notes,
        started_at         = datetime.now(timezone.utc),
        is_billable        = data.get("is_billable", True),
        hourly_rate_applied= data.get("hourly_rate_applied"),
    )
    db.add(session)
    slot.status = "in_progress"
    await db.flush()
    await db.refresh(session)

    return {
        "id":               str(session.id),
        "client_id":        str(session.client_id),
        "project_id":       str(session.project_id) if session.project_id else None,
        "planning_slot_id": str(session.planning_slot_id),
        "activity":         session.activity,
        "started_at":       _aware(session.started_at).isoformat(),
        "is_billable":      session.is_billable,
    }
