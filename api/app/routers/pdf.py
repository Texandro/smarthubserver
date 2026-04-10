# -*- coding: utf-8 -*-
"""
SmartHub — Router PDF
Endpoints de génération PDF pour tous les types de documents.
Le client Qt appelle ces endpoints, le serveur génère et retourne les bytes.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..auth import get_current_user, require_owner
from ..models.auth import User
from ..models.forensics import ForensicsCase
from ..core.database import get_db
from ..services.contract_pdf import (
    generate_lm,
    generate_maintenance,
    generate_fiche_intervention,
    generate_shredding_report,
    generate_forensics_report,
)

router = APIRouter(prefix="/pdf", tags=["pdf"])

NAS_BASE = Path(os.getenv("NAS_BASE_PATH", "/mnt/nas/smarthub/Clients"))


def _safe_name(name: str) -> str:
    import re
    name = re.sub(r'[<>:"/\\|?*]', '-', name)
    return name.strip('. ')[:80]


@router.post("/contract")
async def pdf_contract(
    data: dict,
    _: User = Depends(get_current_user),
):
    """Génère une lettre de mission (tout type) et retourne le PDF."""
    try:
        pdf_bytes = generate_lm(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    filename = data.get("reference", "contrat") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/maintenance")
async def pdf_maintenance(
    data: dict,
    _: User = Depends(get_current_user),
):
    """Génère un contrat de maintenance et retourne le PDF."""
    try:
        pdf_bytes = generate_maintenance(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    filename = data.get("reference", "maintenance") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/fiche-intervention")
async def pdf_fiche_intervention(
    data: dict,
    _: User = Depends(get_current_user),
):
    """Génère une fiche d'intervention atelier et retourne le PDF."""
    try:
        pdf_bytes = generate_fiche_intervention(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    filename = data.get("reference", "fiche_intervention") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/shredding")
async def pdf_shredding(
    data: dict,
    _: User = Depends(get_current_user),
):
    """Génère un rapport d'effacement certifié et retourne le PDF."""
    try:
        pdf_bytes = generate_shredding_report(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    filename = data.get("reference", "shredding") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/forensics")
async def pdf_forensics(
    data: dict,
    _: User = Depends(get_current_user),
):
    """Génère un rapport forensics certifié et retourne le PDF."""
    try:
        pdf_bytes = generate_forensics_report(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    filename = data.get("reference", "forensics") + ".pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/forensics/publish")
async def pdf_forensics_publish(
    data: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_owner),
):
    """
    Génère un rapport forensics, le sauve sur le NAS dans le dossier
    5. Forensics du client, met à jour le case en DB, et retourne le PDF.
    """
    case_id = data.get("id")
    client_name = data.get("client_name", "")

    # ── 1. Générer le PDF ──
    try:
        pdf_bytes = generate_forensics_report(data)
    except KeyError as e:
        raise HTTPException(422, f"Champ manquant : {e}")
    except Exception as e:
        raise HTTPException(500, f"Erreur de génération : {e}")

    # ── 2. Sauvegarder sur le NAS ──
    nas_saved = False
    nas_path_str = None
    reference = data.get("reference", "forensics")
    filename = f"{reference}.pdf"

    if client_name and NAS_BASE.exists():
        client_folder = NAS_BASE / _safe_name(client_name) / "5. Forensics"
        try:
            client_folder.mkdir(parents=True, exist_ok=True)
            pdf_path = client_folder / filename
            pdf_path.write_bytes(pdf_bytes)
            nas_saved = True
            nas_path_str = str(pdf_path).replace("/mnt/nas", "\\\\NAS")
        except Exception as e:
            # On ne crash pas — le PDF est quand même retourné
            print(f"[WARN] Sauvegarde NAS forensics échouée : {e}")

    # ── 3. Mettre à jour le case en DB ──
    if case_id:
        try:
            result = await db.execute(
                select(ForensicsCase).where(ForensicsCase.id == case_id))
            case = result.scalar_one_or_none()
            if case:
                case.final_report_path = nas_path_str or filename
                case.status = "clôturé"
                if not case.closed_at:
                    from datetime import datetime, timezone
                    case.closed_at = datetime.now(timezone.utc)
                # Sauvegarder les phases
                phases = {}
                for k in ["phase1", "phase2", "phase3", "phase4", "phase5", "phase6"]:
                    if k in data:
                        phases[k] = data[k]
                if phases:
                    case.phases_data = phases
                await db.flush()
        except Exception as e:
            print(f"[WARN] Mise à jour case forensics échouée : {e}")

    # ── 4. Retourner le PDF + metadata ──
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-NAS-Saved": "true" if nas_saved else "false",
            "X-NAS-Path": nas_path_str or "",
            "X-PDF-Size": str(len(pdf_bytes)),
        },
    )
