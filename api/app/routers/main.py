from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .core.config import get_settings
from .routers import auth, clients, timetrack, contracts, projects, equipment, forensics, interventions, dashboard
from .routers.equipment import atelier_router
from .routers.nas import router as nas_router
from .routers.nas import router as nas_router
from .routers.pdf import router as pdf_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.app_name} v{settings.app_version} démarré")
    print(f"   Auth : X-API-Key header requis sur tous les endpoints (sauf /health et /api/v1/auth/setup)")
    yield
    print("👋 Arrêt propre")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
## SmartHub API — Smartclick BV

### Auth
Tous les endpoints nécessitent un header `X-API-Key`.
Au premier démarrage : `POST /api/v1/auth/setup` (sans auth) pour générer la clé owner.

### Rôles
- **owner** : accès complet
- **technicien** : dashboard, interventions, atelier, timetrack (pas contrats/finance/clients/forensics)
    """,
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

PREFIX = "/api/v1"

app.include_router(auth.router,          prefix=PREFIX)
app.include_router(clients.router,       prefix=PREFIX)
app.include_router(timetrack.router,     prefix=PREFIX)
app.include_router(contracts.router,     prefix=PREFIX)
app.include_router(projects.router,      prefix=PREFIX)
app.include_router(equipment.router,     prefix=PREFIX)
app.include_router(atelier_router,       prefix=PREFIX)   # alias /atelier/ → equipment
app.include_router(forensics.router,     prefix=PREFIX)
app.include_router(interventions.router, prefix=PREFIX)
app.include_router(dashboard.router,     prefix=PREFIX)
app.include_router(nas_router,           prefix=PREFIX)
app.include_router(pdf_router, 		 prefix=PREFIX)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/", tags=["system"])
async def root():
    return {
        "message": "SmartHub API",
        "docs":    "/docs",
        "setup":   "POST /api/v1/auth/setup  (premier démarrage uniquement)",
    }
