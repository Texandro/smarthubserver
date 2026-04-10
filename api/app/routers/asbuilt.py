# -*- coding: utf-8 -*-
"""
SmartHub — Router As-Built
Infrastructure + Stack logicielle + Documentation dev
"""
from __future__ import annotations
import uuid, re, json
from typing import Optional
from datetime import date as _date, datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from ..core.database import get_db
from ..auth import require_owner, get_current_user
from ..models.auth import User
from ..models.asbuilt import (
    AsbuiltDocument, AsbuiltDocStatus, AsbuiltDocType, AsbuiltHistory,
    InfraServer, InfraVpnLink,
    StackDockerContainer, StackSystemService, StackDeployedScript,
    DevApplication, DevDocumentation, DocLevel,
    ServerType,
)
from ..models.client import Client

router = APIRouter()

PREFIX = "/api/v1"

# ── Helpers ───────────────────────────────────────────────────

SECRET_PATTERNS = re.compile(
    r'(password|secret|key|token|api_key|passwd|pwd|credential)',
    re.IGNORECASE
)

def _mask_secrets(env_vars: list) -> list:
    """Masque les secrets dans les variables d'environnement."""
    masked = []
    for item in env_vars:
        if isinstance(item, dict):
            name = item.get("name", "") or item.get("key", "")
            if SECRET_PATTERNS.search(name):
                item = {**item, "value": "••••••• (voir vault)"}
        masked.append(item)
    return masked


def _doc_dict(doc: AsbuiltDocument) -> dict:
    return {
        "id":           str(doc.id),
        "client_id":    str(doc.client_id),
        "doc_type":     doc.doc_type,
        "title":        doc.title,
        "version":      doc.version,
        "status":       doc.status,
        "nas_path":     doc.nas_path,
        "notes":        doc.notes,
        "generated_at": doc.generated_at.isoformat() if doc.generated_at else None,
        "created_at":   doc.created_at.isoformat(),
        "updated_at":   doc.updated_at.isoformat(),
    }


def _server_dict(s: InfraServer) -> dict:
    return {
        "id":                   str(s.id),
        "client_id":            str(s.client_id),
        "asbuilt_doc_id":       str(s.asbuilt_doc_id) if s.asbuilt_doc_id else None,
        "hostname":             s.hostname,
        "server_type":          s.server_type,
        "provider":             s.provider,
        "datacenter":           s.datacenter,
        "reference_provider":   s.reference_provider,
        "ip_public":            s.ip_public,
        "ip_private":           s.ip_private,
        "os":                   s.os,
        "cpu":                  s.cpu,
        "ram":                  s.ram,
        "storage":              s.storage,
        "role":                 s.role,
        "date_mise_en_service": s.date_mise_en_service.isoformat() if s.date_mise_en_service else None,
        "contract_id":          str(s.contract_id) if s.contract_id else None,
        "rack_equipment_id":    str(s.rack_equipment_id) if s.rack_equipment_id else None,
        "notes":                s.notes,
        "created_at":           s.created_at.isoformat(),
    }


def _vpn_dict(v: InfraVpnLink) -> dict:
    return {
        "id":             str(v.id),
        "client_id":      str(v.client_id),
        "asbuilt_doc_id": str(v.asbuilt_doc_id) if v.asbuilt_doc_id else None,
        "name":           v.name,
        "vpn_type":       v.vpn_type,
        "protocol":       v.protocol,
        "endpoint_a":     v.endpoint_a,
        "endpoint_b":     v.endpoint_b,
        "subnet_a":       v.subnet_a,
        "subnet_b":       v.subnet_b,
        "port":           v.port,
        "encryption":     v.encryption,
        "status":         v.status,
        "notes":          v.notes,
    }


def _container_dict(c: StackDockerContainer, show_secrets: bool = False) -> dict:
    env = c.env_vars if show_secrets else _mask_secrets(c.env_vars or [])
    return {
        "id":             str(c.id),
        "server_id":      str(c.server_id),
        "service_name":   c.service_name,
        "image":          c.image,
        "version_tag":    c.version_tag,
        "ports":          c.ports,
        "volumes":        c.volumes,
        "env_vars":       env,
        "networks":       c.networks,
        "depends_on":     c.depends_on,
        "restart_policy": c.restart_policy,
        "description":    c.description,
        "url_access":     c.url_access,
    }


# ── As-Built Documents ────────────────────────────────────────

@router.get("/asbuilt/")
async def list_documents(
    client_id: Optional[str] = None,
    doc_type:  Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(AsbuiltDocument)
    if client_id:
        q = q.where(AsbuiltDocument.client_id == client_id)
    if doc_type:
        q = q.where(AsbuiltDocument.doc_type == doc_type)
    q = q.order_by(AsbuiltDocument.updated_at.desc())
    result = await db.execute(q)
    return [_doc_dict(d) for d in result.scalars().all()]


@router.post("/asbuilt/", status_code=201)
async def create_document(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]:
        data.pop(f, None)
    doc = AsbuiltDocument(**data)
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return _doc_dict(doc)


@router.get("/asbuilt/{doc_id}")
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    r = await db.execute(select(AsbuiltDocument).where(AsbuiltDocument.id == doc_id))
    doc = r.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    return _doc_dict(doc)


@router.patch("/asbuilt/{doc_id}")
async def update_document(
    doc_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    r = await db.execute(select(AsbuiltDocument).where(AsbuiltDocument.id == doc_id))
    doc = r.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    for f in ["id", "created_at", "updated_at", "client_id"]:
        data.pop(f, None)
    for k, v in data.items():
        setattr(doc, k, v)
    await db.commit()
    await db.refresh(doc)
    return _doc_dict(doc)


@router.delete("/asbuilt/{doc_id}", status_code=204)
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    r = await db.execute(select(AsbuiltDocument).where(AsbuiltDocument.id == doc_id))
    doc = r.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "Document introuvable")
    await db.delete(doc)
    await db.commit()


# ── Infrastructure : Serveurs ─────────────────────────────────

@router.get("/asbuilt/servers/")
async def list_servers(
    client_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(InfraServer)
    if client_id:
        q = q.where(InfraServer.client_id == client_id)
    q = q.order_by(InfraServer.hostname)
    r = await db.execute(q)
    return [_server_dict(s) for s in r.scalars().all()]


@router.post("/asbuilt/servers/", status_code=201)
async def create_server(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]:
        data.pop(f, None)
    if data.get("date_mise_en_service") and isinstance(data["date_mise_en_service"], str):
        try:
            data["date_mise_en_service"] = _date.fromisoformat(data["date_mise_en_service"])
        except ValueError:
            data.pop("date_mise_en_service", None)
    s = InfraServer(**data)
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return _server_dict(s)


@router.get("/asbuilt/servers/{server_id}")
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    r = await db.execute(
        select(InfraServer)
        .options(
            selectinload(InfraServer.docker_containers),
            selectinload(InfraServer.system_services),
            selectinload(InfraServer.deployed_scripts),
        )
        .where(InfraServer.id == server_id)
    )
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Serveur introuvable")
    d = _server_dict(s)
    d["docker_containers"] = [_container_dict(c) for c in s.docker_containers]
    d["system_services"]   = [{"id": str(x.id), "name": x.name, "service_type": x.service_type,
                                "version": x.version, "port": x.port, "description": x.description,
                                "auto_start": x.auto_start} for x in s.system_services]
    d["deployed_scripts"]  = [{"id": str(x.id), "name": x.name, "language": x.language,
                                "path": x.path, "purpose": x.purpose, "trigger": x.trigger,
                                "cron_schedule": x.cron_schedule} for x in s.deployed_scripts]
    return d


@router.patch("/asbuilt/servers/{server_id}")
async def update_server(
    server_id: str,
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    r = await db.execute(select(InfraServer).where(InfraServer.id == server_id))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Serveur introuvable")
    for f in ["id", "created_at", "updated_at", "client_id"]:
        data.pop(f, None)
    if data.get("date_mise_en_service") and isinstance(data["date_mise_en_service"], str):
        try:
            data["date_mise_en_service"] = _date.fromisoformat(data["date_mise_en_service"])
        except ValueError:
            data.pop("date_mise_en_service", None)
    for k, v in data.items():
        setattr(s, k, v)
    await db.commit()
    await db.refresh(s)
    return _server_dict(s)


@router.delete("/asbuilt/servers/{server_id}", status_code=204)
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    r = await db.execute(select(InfraServer).where(InfraServer.id == server_id))
    s = r.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Serveur introuvable")
    await db.delete(s)
    await db.commit()


# ── Infrastructure : VPN ─────────────────────────────────────

@router.get("/asbuilt/vpn/")
async def list_vpn(
    client_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    q = select(InfraVpnLink)
    if client_id:
        q = q.where(InfraVpnLink.client_id == client_id)
    r = await db.execute(q)
    return [_vpn_dict(v) for v in r.scalars().all()]


@router.post("/asbuilt/vpn/", status_code=201)
async def create_vpn(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]:
        data.pop(f, None)
    v = InfraVpnLink(**data)
    db.add(v)
    await db.commit()
    await db.refresh(v)
    return _vpn_dict(v)


@router.patch("/asbuilt/vpn/{vpn_id}")
async def update_vpn(vpn_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(InfraVpnLink).where(InfraVpnLink.id == vpn_id))
    v = r.scalar_one_or_none()
    if not v: raise HTTPException(404, "VPN introuvable")
    for f in ["id", "created_at", "updated_at", "client_id"]: data.pop(f, None)
    for k, val in data.items(): setattr(v, k, val)
    await db.commit(); await db.refresh(v)
    return _vpn_dict(v)


@router.delete("/asbuilt/vpn/{vpn_id}", status_code=204)
async def delete_vpn(vpn_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(InfraVpnLink).where(InfraVpnLink.id == vpn_id))
    v = r.scalar_one_or_none()
    if not v: raise HTTPException(404, "VPN introuvable")
    await db.delete(v); await db.commit()


# ── Stack : Docker containers ─────────────────────────────────

@router.post("/asbuilt/servers/{server_id}/docker/", status_code=201)
async def create_container(
    server_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]: data.pop(f, None)
    data["server_id"] = server_id
    # Stocker les secrets chiffrés séparément
    raw_env = data.get("env_vars", [])
    data["env_vars"] = _mask_secrets(raw_env)
    c = StackDockerContainer(**data)
    db.add(c); await db.commit(); await db.refresh(c)
    return _container_dict(c)


@router.patch("/asbuilt/docker/{container_id}")
async def update_container(
    container_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    r = await db.execute(select(StackDockerContainer).where(StackDockerContainer.id == container_id))
    c = r.scalar_one_or_none()
    if not c: raise HTTPException(404, "Container introuvable")
    for f in ["id", "created_at", "updated_at", "server_id"]: data.pop(f, None)
    if "env_vars" in data:
        data["env_vars"] = _mask_secrets(data["env_vars"])
    for k, v in data.items(): setattr(c, k, v)
    await db.commit(); await db.refresh(c)
    return _container_dict(c)


@router.delete("/asbuilt/docker/{container_id}", status_code=204)
async def delete_container(
    container_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    r = await db.execute(select(StackDockerContainer).where(StackDockerContainer.id == container_id))
    c = r.scalar_one_or_none()
    if not c: raise HTTPException(404, "Container introuvable")
    await db.delete(c); await db.commit()


# ── Import docker-compose ─────────────────────────────────────

@router.post("/asbuilt/servers/{server_id}/import-compose/")
async def import_docker_compose(
    server_id: str,
    content: str,   # contenu YAML en string
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """Parse un docker-compose.yml et crée les containers."""
    try:
        import yaml
        compose = yaml.safe_load(content)
    except Exception as e:
        raise HTTPException(400, f"YAML invalide : {e}")

    services = compose.get("services", {})
    if not services:
        raise HTTPException(400, "Aucun service trouvé dans le docker-compose")

    created = []
    for svc_name, svc in services.items():
        # Parser les ports
        ports = []
        for p in (svc.get("ports") or []):
            if isinstance(p, str) and ":" in p:
                parts = p.split(":")
                ports.append({"host_port": parts[0], "container_port": parts[-1].split("/")[0],
                               "protocol": "tcp" if "/udp" not in p else "udp"})
            elif isinstance(p, int):
                ports.append({"host_port": str(p), "container_port": str(p), "protocol": "tcp"})

        # Parser les volumes
        volumes = []
        for v in (svc.get("volumes") or []):
            if isinstance(v, str) and ":" in v:
                parts = v.split(":")
                volumes.append({"host_path": parts[0], "container_path": parts[1],
                                 "mode": parts[2] if len(parts) > 2 else "rw"})

        # Parser env_vars avec masquage secrets
        env_vars = []
        for e in (svc.get("environment") or []):
            if isinstance(e, str) and "=" in e:
                k, _, v = e.partition("=")
                env_vars.append({"name": k, "value": v})
            elif isinstance(e, dict):
                for k, v in e.items():
                    env_vars.append({"name": k, "value": str(v) if v else ""})

        # Image + tag
        image_full = svc.get("image", "")
        image, _, tag = image_full.partition(":")
        if not tag:
            tag = "latest"

        container = StackDockerContainer(
            server_id      = server_id,
            service_name   = svc_name,
            image          = image or image_full,
            version_tag    = tag,
            ports          = ports,
            volumes        = volumes,
            env_vars       = _mask_secrets(env_vars),
            networks       = list((svc.get("networks") or {}).keys()) if isinstance(svc.get("networks"), dict) else (svc.get("networks") or []),
            depends_on     = list((svc.get("depends_on") or {}).keys()) if isinstance(svc.get("depends_on"), dict) else (svc.get("depends_on") or []),
            restart_policy = svc.get("restart", "unless-stopped"),
        )
        db.add(container)
        created.append(svc_name)

    await db.commit()
    return {"imported": len(created), "services": created}


# ── Stack : Services système ──────────────────────────────────

@router.post("/asbuilt/servers/{server_id}/services/", status_code=201)
async def create_service(
    server_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]: data.pop(f, None)
    data["server_id"] = server_id
    s = StackSystemService(**data)
    db.add(s); await db.commit(); await db.refresh(s)
    return {"id": str(s.id), "name": s.name, "service_type": s.service_type,
            "version": s.version, "port": s.port, "description": s.description, "auto_start": s.auto_start}


@router.patch("/asbuilt/services/{service_id}")
async def update_service(service_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(StackSystemService).where(StackSystemService.id == service_id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Service introuvable")
    for f in ["id", "created_at", "updated_at", "server_id"]: data.pop(f, None)
    for k, v in data.items(): setattr(s, k, v)
    await db.commit(); await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


@router.delete("/asbuilt/services/{service_id}", status_code=204)
async def delete_service(service_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(StackSystemService).where(StackSystemService.id == service_id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Service introuvable")
    await db.delete(s); await db.commit()


# ── Stack : Scripts ───────────────────────────────────────────

@router.post("/asbuilt/servers/{server_id}/scripts/", status_code=201)
async def create_script(
    server_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]: data.pop(f, None)
    data["server_id"] = server_id
    s = StackDeployedScript(**data)
    db.add(s); await db.commit(); await db.refresh(s)
    return {"id": str(s.id), "name": s.name, "language": s.language, "trigger": s.trigger}


@router.patch("/asbuilt/scripts/{script_id}")
async def update_script(script_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(StackDeployedScript).where(StackDeployedScript.id == script_id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Script introuvable")
    for f in ["id", "created_at", "updated_at", "server_id"]: data.pop(f, None)
    for k, v in data.items(): setattr(s, k, v)
    await db.commit(); await db.refresh(s)
    return {"id": str(s.id), "name": s.name}


@router.delete("/asbuilt/scripts/{script_id}", status_code=204)
async def delete_script(script_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(StackDeployedScript).where(StackDeployedScript.id == script_id))
    s = r.scalar_one_or_none()
    if not s: raise HTTPException(404, "Script introuvable")
    await db.delete(s); await db.commit()


# ── Documentation dev : Applications ─────────────────────────

@router.get("/asbuilt/dev/apps/")
async def list_apps(
    client_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user),
):
    q = select(DevApplication)
    if client_id:
        q = q.where(DevApplication.client_id == client_id)
    r = await db.execute(q)
    apps = r.scalars().all()
    return [{"id": str(a.id), "client_id": str(a.client_id), "name": a.name,
             "description": a.description, "repo_url": a.repo_url,
             "tech_stack": a.tech_stack, "deployed_on": a.deployed_on} for a in apps]


@router.post("/asbuilt/dev/apps/", status_code=201)
async def create_app(
    data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner),
):
    for f in ["id", "created_at", "updated_at"]: data.pop(f, None)
    a = DevApplication(**data)
    db.add(a); await db.commit(); await db.refresh(a)
    return {"id": str(a.id), "name": a.name}


@router.patch("/asbuilt/dev/apps/{app_id}")
async def update_app(app_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(DevApplication).where(DevApplication.id == app_id))
    a = r.scalar_one_or_none()
    if not a: raise HTTPException(404, "Application introuvable")
    for f in ["id", "created_at", "updated_at", "client_id"]: data.pop(f, None)
    for k, v in data.items(): setattr(a, k, v)
    await db.commit(); await db.refresh(a)
    return {"id": str(a.id), "name": a.name}


@router.delete("/asbuilt/dev/apps/{app_id}", status_code=204)
async def delete_app(app_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(DevApplication).where(DevApplication.id == app_id))
    a = r.scalar_one_or_none()
    if not a: raise HTTPException(404, "Application introuvable")
    await db.delete(a); await db.commit()


# ── Documentation dev : Génération IA ────────────────────────

@router.post("/asbuilt/dev/apps/{app_id}/generate-docs/")
async def generate_docs(
    app_id: str,
    data: dict,  # {"level": "opensource"|"client"|"internal", "source_content": "..."}
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """
    Génère la documentation via l'API Claude.
    source_content = contenu analysé (README, code scanné, etc.)
    """
    r = await db.execute(select(DevApplication).where(DevApplication.id == app_id))
    app = r.scalar_one_or_none()
    if not app: raise HTTPException(404, "Application introuvable")

    level = data.get("level", "client")
    source = data.get("source_content", "")

    level_instructions = {
        "opensource": """Génère une documentation COMPLÈTE niveau Open Source incluant :
            1. Introduction (description, contexte, objectif)
            2. Architecture technique (composants, technologies, choix techniques)
            3. Modèle de données (entités, relations)
            4. API complète (tous endpoints, paramètres, réponses)
            5. Composants (chaque module : rôle, entrées/sorties)
            6. Flux de données
            7. Déploiement (prérequis, installation, configuration)
            8. Tests (stratégie, procédures)
            9. Maintenance (MAJ, backup, monitoring, troubleshooting)
            10. Dépendances complètes avec versions
            Réponds en JSON avec ces 10 sections comme clés.""",

        "client": """Génère une documentation FONCTIONNELLE niveau client incluant :
            1. Présentation fonctionnelle
            2. Guide utilisateur (workflows principaux)
            3. Configuration (paramètres configurables)
            4. API publique (si applicable)
            5. FAQ / Troubleshooting
            N'inclus PAS : architecture interne, code, déploiement.
            Réponds en JSON avec ces 5 sections comme clés.""",

        "internal": """Génère une documentation OPÉRATIONNELLE interne incluant :
            1. Résumé (quoi, pour qui, où déployé)
            2. Déploiement (commandes concrètes)
            3. Accès (URLs, credentials — référence vault pour secrets)
            4. Particularités (pièges, workarounds connus)
            Réponds en JSON avec ces 4 sections comme clés.""",
    }

    prompt = f"""Tu es un expert en documentation technique.
Voici les informations sur l'application "{app.name}" :
Description : {app.description or 'non fournie'}
Stack technique : {json.dumps(app.tech_stack)}
Contenu source analysé :
---
{source[:8000]}
---

{level_instructions.get(level, level_instructions['client'])}

IMPORTANT : Réponds UNIQUEMENT avec le JSON, sans markdown, sans backticks."""

    # Appel API Claude
    import httpx as _httpx
    try:
        resp = _httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json"},
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=60,
        )
        resp.raise_for_status()
        raw = resp.json()["content"][0]["text"]
        # Nettoyer JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        content = json.loads(raw)
    except Exception as e:
        raise HTTPException(500, f"Erreur génération IA : {e}")

    # Sauver en DB
    existing = await db.execute(
        select(DevDocumentation).where(
            DevDocumentation.app_id == app_id,
            DevDocumentation.level  == level
        )
    )
    doc = existing.scalar_one_or_none()
    now = datetime.utcnow()
    if doc:
        doc.content         = content
        doc.ai_generated    = True
        doc.ai_model        = "claude-sonnet-4-20250514"
        doc.ai_generated_at = now
        doc.version         += 1
    else:
        doc = DevDocumentation(
            app_id          = app_id,
            level           = level,
            content         = content,
            ai_generated    = True,
            ai_model        = "claude-sonnet-4-20250514",
            ai_generated_at = now,
        )
        db.add(doc)

    await db.commit()
    await db.refresh(doc)
    return {"id": str(doc.id), "level": level, "version": doc.version, "content": content}


@router.get("/asbuilt/dev/apps/{app_id}/docs/")
async def get_app_docs(app_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(
        select(DevDocumentation).where(DevDocumentation.app_id == app_id)
    )
    docs = r.scalars().all()
    return [{"id": str(d.id), "level": d.level, "version": d.version,
             "ai_generated": d.ai_generated, "ai_generated_at": d.ai_generated_at.isoformat() if d.ai_generated_at else None,
             "content": d.content} for d in docs]


@router.patch("/asbuilt/dev/docs/{doc_id}")
async def update_doc_content(doc_id: str, data: dict,
    db: AsyncSession = Depends(get_db), _: User = Depends(require_owner)):
    r = await db.execute(select(DevDocumentation).where(DevDocumentation.id == doc_id))
    d = r.scalar_one_or_none()
    if not d: raise HTTPException(404, "Documentation introuvable")
    if "content" in data:
        d.content = data["content"]
    if "validated_by" in data:
        d.validated_by = data["validated_by"]
        d.validated_at = datetime.utcnow()
    await db.commit(); await db.refresh(d)
    return {"id": str(d.id), "level": d.level, "version": d.version}


# ── Historique ────────────────────────────────────────────────

@router.get("/asbuilt/{doc_id}/history/")
async def get_history(doc_id: str,
    db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    r = await db.execute(
        select(AsbuiltHistory)
        .where(AsbuiltHistory.document_id == doc_id)
        .order_by(AsbuiltHistory.version.desc())
    )
    return [{"id": str(h.id), "version": h.version, "nas_path": h.nas_path,
             "change_summary": h.change_summary, "created_at": h.created_at.isoformat()}
            for h in r.scalars().all()]
