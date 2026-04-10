# SmartHub — Backend v1.1 + Auth

## Structure des fichiers

```
/srv/smarthub/
├── .env
├── docker-compose.yml
├── deploy.sh                   ← Script de déploiement
├── db/
│   ├── Dockerfile
│   ├── 001_schema.sql          ← Schéma original (existant)
│   └── 002_auth_and_interventions.sql  ← NOUVEAU : auth + on_site_interventions + as_built
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── auth.py             ← NOUVEAU : validation X-API-Key
│       ├── core/
│       │   ├── config.py
│       │   └── database.py
│       ├── models/
│       │   ├── auth.py         ← NOUVEAU : User + APIKey
│       │   ├── intervention.py ← NOUVEAU : OnSiteIntervention
│       │   ├── client.py
│       │   ├── contract.py
│       │   ├── project.py
│       │   ├── equipment.py
│       │   ├── forensics.py
│       │   └── timetrack.py
│       └── routers/
│           ├── auth.py         ← NOUVEAU
│           ├── clients.py      ← Mis à jour : fiche 360° + auth
│           ├── timetrack.py    ← Mis à jour : start/stop/active + auth
│           ├── contracts.py    ← Mis à jour : owner only + auth
│           ├── projects.py     ← Mis à jour : auth
│           ├── forensics.py    ← Mis à jour : alias /missions/ + auth
│           ├── equipment.py    ← Mis à jour : alias /atelier/ + auth
│           ├── interventions.py ← NOUVEAU : on-site interventions
│           └── dashboard.py    ← Mis à jour : vue owner vs technicien
└── caddy/
    └── Caddyfile
```

## Déploiement (DB existante)

```bash
# 1. Copier les nouveaux fichiers sur le NUC
scp -r smarthub/ root@smartdocker:/srv/

# 2. Rendre le script exécutable et déployer
ssh root@smartdocker
cd /srv/smarthub
chmod +x deploy.sh
bash deploy.sh
```

Le script :
- Rebuild les images Docker
- Applique la migration 002 si la DB existe déjà
- Génère la clé API owner au premier démarrage
- Affiche la clé en clair UNE SEULE FOIS

## Déploiement (DB from scratch)

```bash
cd /srv/smarthub
docker compose down -v        # ⚠️ Supprime les données !
docker compose build
docker compose up -d
sleep 10
curl -X POST http://localhost:8080/api/v1/auth/setup
```

## Auth — Endpoints

| Endpoint | Auth | Description |
|----------|------|-------------|
| `GET /health` | ❌ | Santé API |
| `POST /api/v1/auth/setup` | ❌ | Génère clé owner (1 seule fois) |
| `GET /api/v1/auth/me` | ✅ | Infos utilisateur courant |
| `GET /api/v1/auth/keys` | ✅ | Lister ses clés |
| `POST /api/v1/auth/keys` | ✅ owner | Créer une clé |
| `DELETE /api/v1/auth/keys/{id}` | ✅ | Révoquer une clé |
| `GET /api/v1/auth/users` | ✅ owner | Lister utilisateurs |
| `POST /api/v1/auth/users` | ✅ owner | Créer un technicien |

## Rôles

| Endpoint | Owner | Technicien |
|----------|-------|------------|
| Clients (CRUD) | ✅ | ✅ lecture |
| Contrats | ✅ | ❌ |
| Finance | ✅ | ❌ |
| Forensics | ✅ | ❌ |
| Projets | ✅ | ✅ |
| Interventions on-site | ✅ | ✅ |
| Atelier/Equipment | ✅ | ✅ |
| Timetrack | ✅ | ✅ |
| Dashboard | ✅ complet | ✅ réduit |

## Routes Qt → Backend (mapping)

| Qt appelle | Backend répond |
|-----------|---------------|
| `GET /clients/` | ✅ |
| `GET /clients/{id}/contracts` | ✅ owner only |
| `GET /clients/{id}/interventions` | ✅ |
| `GET /clients/{id}/atelier` | ✅ |
| `GET /clients/{id}/forensics` | ✅ owner only |
| `GET /clients/{id}/timetrack` | ✅ |
| `POST /timetrack/start` | ✅ |
| `POST /timetrack/stop` | ✅ |
| `GET /timetrack/active` | ✅ |
| `GET /timetrack/` | ✅ |
| `GET /interventions/` | ✅ |
| `POST /interventions/` | ✅ |
| `GET /atelier/` | ✅ (alias /equipment/) |
| `GET /forensics/missions/` | ✅ (alias /forensics/) |
| `POST /forensics/missions/` | ✅ |
| `GET /contracts/` | ✅ owner |
| `GET /projects/` | ✅ |
| `GET /dashboard/` | ✅ |

## Configurer le Qt

Dans `smarthub/config.py` :
```python
DEFAULT_API_BASE = "http://10.0.2.202:8080/api/v1"
# ou via https si tu passes par Caddy :
# DEFAULT_API_BASE = "https://hub.smartclick.be/api/v1"
```

La clé API est stockée dans QSettings (registre Windows).
Au premier lancement, le dialog de connexion s'affiche.

## Créer une clé pour un futur technicien

```bash
# Avec curl depuis le NUC
curl -X POST http://localhost:8080/api/v1/auth/users \
  -H "X-API-Key: <ta_cle_owner>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Jean Technicien", "email": "jean@smartclick.be", "role": "technicien"}'
```
