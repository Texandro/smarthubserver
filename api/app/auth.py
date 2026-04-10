"""
SmartHub — Auth via API Key
Header: X-API-Key: <raw_key>
La clé est hashée SHA256 côté client avant stockage.
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from .core.database import get_db
from .models.auth import User, APIKey, UserRole

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_key(raw_key: str) -> str:
    """SHA256 d'une clé brute."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> tuple[str, str]:
    """Génère (raw_key, hash). Retourner raw_key UNE SEULE FOIS au client."""
    raw = f"smh_{secrets.token_urlsafe(32)}"
    return raw, hash_key(raw)


async def get_current_user(
    api_key: Optional[str] = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Valide la clé API et retourne l'utilisateur associé."""
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API manquante. Header: X-API-Key",
        )

    key_hash = hash_key(api_key)

    result = await db.execute(
        select(APIKey, User)
        .join(User, APIKey.user_id == User.id)
        .where(
            APIKey.key_hash == key_hash,
            APIKey.is_active == True,
            User.is_active == True,
        )
    )
    row = result.first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou désactivée.",
        )

    api_key_obj, user = row

    # Mise à jour last_used_at (non bloquant)
    await db.execute(
        update(APIKey)
        .where(APIKey.id == api_key_obj.id)
        .values(last_used_at=datetime.now(timezone.utc))
    )

    return user


def require_owner(current_user: User = Depends(get_current_user)) -> User:
    """Endpoint réservé au rôle owner."""
    if current_user.role != UserRole.owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé au propriétaire du compte.",
        )
    return current_user


def require_any(current_user: User = Depends(get_current_user)) -> User:
    """Tout utilisateur authentifié."""
    return current_user
