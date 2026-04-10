"""
SmartHub — Router Auth
POST /api/v1/auth/setup     → Premier démarrage : génère la clé owner (une seule fois)
POST /api/v1/auth/keys      → Créer une nouvelle clé (owner only)
GET  /api/v1/auth/keys      → Lister ses clés
DELETE /api/v1/auth/keys/{id} → Révoquer une clé
GET  /api/v1/auth/me        → Infos utilisateur courant
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy import select, update
from uuid import UUID

from ..core.database import get_db
from ..models.auth import User, APIKey, UserRole
from ..auth import get_current_user, require_owner, generate_key, hash_key

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/setup", include_in_schema=True)
async def setup_first_key(db: AsyncSession = Depends(get_db)):
    """
    Génère la première clé API pour l'owner.
    Endpoint non protégé MAIS ne fonctionne que s'il n'existe aucune clé active.
    À appeler UNE SEULE FOIS au premier démarrage.
    """
    # Vérifier qu'il n'existe pas déjà de clés
    existing = await db.execute(select(APIKey).where(APIKey.is_active == True))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Des clés API existent déjà. Utilisez /auth/keys pour en créer de nouvelles."
        )

    # Trouver l'owner
    owner = await db.execute(
        select(User).where(User.role == UserRole.owner, User.is_active == True)
    )
    user = owner.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=500, detail="Aucun utilisateur owner trouvé en base.")

    raw_key, hashed = generate_key()
    api_key = APIKey(
        user_id  = user.id,
        key_hash = hashed,
        name     = "Clé initiale — Setup",
    )
    db.add(api_key)
    await db.flush()

    return {
        "message"     : "✅ Clé owner créée. Copiez-la maintenant — elle ne sera plus affichée.",
        "api_key"     : raw_key,
        "user"        : user.name,
        "role"        : user.role,
        "key_id"      : str(api_key.id),
        "instructions": "Ajoutez X-API-Key: <votre_clé> dans les headers de toutes vos requêtes.",
    }


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Infos de l'utilisateur authentifié."""
    return {
        "id"    : str(current_user.id),
        "name"  : current_user.name,
        "email" : current_user.email,
        "role"  : current_user.role,
    }


@router.get("/keys")
async def list_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste les clés API de l'utilisateur courant (owner voit toutes)."""
    if current_user.role == UserRole.owner:
        result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    else:
        result = await db.execute(
            select(APIKey).where(APIKey.user_id == current_user.id)
        )
    keys = result.scalars().all()
    return [
        {
            "id"          : str(k.id),
            "name"        : k.name,
            "user_id"     : str(k.user_id),
            "is_active"   : k.is_active,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "created_at"  : k.created_at.isoformat(),
        }
        for k in keys
    ]


@router.post("/keys")
async def create_key(
    data: dict,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle clé API (owner only).
    Body: {"name": "Timer Overlay", "user_id": "<uuid>"}  ← user_id optionnel (défaut = soi-même)
    """
    name    = data.get("name", "Nouvelle clé")
    user_id = data.get("user_id", str(current_user.id))

    # Vérifier que l'user cible existe
    target = await db.execute(select(User).where(User.id == user_id))
    if not target.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Utilisateur introuvable.")

    raw_key, hashed = generate_key()
    api_key = APIKey(user_id=user_id, key_hash=hashed, name=name)
    db.add(api_key)
    await db.flush()

    return {
        "message" : "✅ Nouvelle clé créée. Copiez-la maintenant.",
        "api_key" : raw_key,
        "name"    : name,
        "key_id"  : str(api_key.id),
    }


@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Révoque une clé API."""
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Clé introuvable.")
    # Owner peut révoquer n'importe quelle clé, technicien seulement les siennes
    if current_user.role != UserRole.owner and key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Non autorisé.")

    key.is_active = False
    return {"message": "Clé révoquée.", "key_id": str(key_id)}


@router.get("/users")
async def list_users(
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les utilisateurs (owner only)."""
    result = await db.execute(select(User).order_by(User.name))
    users = result.scalars().all()
    return [
        {
            "id"        : str(u.id),
            "name"      : u.name,
            "email"     : u.email,
            "role"      : u.role,
            "is_active" : u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.post("/users")
async def create_user(
    data: dict,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
):
    """Crée un nouvel utilisateur (technicien) + sa première clé API."""
    user = User(
        name  = data["name"],
        email = data["email"],
        role  = UserRole(data.get("role", "technicien")),
    )
    db.add(user)
    await db.flush()

    raw_key, hashed = generate_key()
    api_key = APIKey(
        user_id  = user.id,
        key_hash = hashed,
        name     = f"Clé initiale — {user.name}",
    )
    db.add(api_key)
    await db.flush()

    return {
        "message"  : f"✅ Utilisateur {user.name} créé.",
        "user_id"  : str(user.id),
        "api_key"  : raw_key,
        "role"     : user.role,
    }

@router.get("/enums")
async def get_enums(db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    """Retourne toutes les valeurs d'enums pour peupler les ComboBox Qt."""
    enums = {}
    result = await db.execute(text("""
        SELECT t.typname, e.enumlabel
        FROM pg_type t JOIN pg_enum e ON t.oid = e.enumtypid
        ORDER BY t.typname, e.enumsortorder
    """))
    for typname, enumlabel in result.fetchall():
        enums.setdefault(typname, []).append(enumlabel)
    return enums
