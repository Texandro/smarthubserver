# Smartclick ERP — Setup

## Structure sur le NUC

```
/srv/
  ├── stack/                  ← Kimai (existant, inchangé)
  ├── traefik/                ← acme.json (ignoré)
  └── smarthub/         ← CE DOSSIER
        ├── docker-compose.yml
        ├── .env
        ├── db/
        │     ├── Dockerfile
        │     └── 001_schema.sql
        └── caddy/
              └── Caddyfile
```

## Démarrage initial

```bash
# 1. Copier le dossier sur le NUC
scp -r smarthub/ root@smartdocker:/srv/

# 2. Créer le .env
cd /srv/smarthub
cp .env.example .env
nano .env   # remplir les passwords

# 3. DNS — Ajouter A record chez ton registrar
#    hub.smartclick.be      → IP publique du NUC
#    pgadmin.smartclick.be  → IP publique du NUC

# 4. Démarrer
docker compose up -d

# 5. Vérifier
docker compose ps
docker compose logs caddy
```

## URLs

| Service  | URL                              | Notes                        |
|----------|----------------------------------|------------------------------|
| ERP      | https://hub.smartclick.be        | App principale (Electron)    |
| pgAdmin  | https://pgadmin.smartclick.be    | Accès réseau local seulement |

## Commandes utiles

```bash
# Entrer dans le container DB avec nano
docker exec -it smarthub-db bash

# Connexion psql directe
docker exec -it smarthub-db psql -U smarthub -d smarthub

# Voir les logs Caddy
docker compose logs -f caddy

# Backup DB
docker exec smarthub-db pg_dump -U smarthub smarthub > backup_$(date +%Y%m%d).sql

# Rebuild après modif Dockerfile
docker compose build postgres
docker compose up -d postgres
```

## Variables d'environnement (.env)

```env
DB_PASSWORD=         # Password PostgreSQL
PGADMIN_PASSWORD=    # Password pgAdmin
SECRET_KEY=          # JWT secret (pour FastAPI — étape suivante)
```
