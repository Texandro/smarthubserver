#!/bin/bash
# ============================================================
# SmartHub — Script de déploiement complet
# À exécuter sur le NUC : bash deploy.sh
# ============================================================
set -e

echo "============================================"
echo " SmartHub — Déploiement v1.1"
echo "============================================"

cd /srv/smarthub

# 1. Arrêter l'API (pas la DB — on garde les données)
echo ""
echo "⏹  Arrêt de l'API..."
docker compose stop api

# 2. Rebuild image API (nouveau code)
echo ""
echo "🔨 Build image API..."
docker compose build api

# 3. Rebuild image PostgreSQL (nouveau 002_*.sql)
echo ""
echo "🔨 Build image PostgreSQL..."
docker compose build postgres

# 4. Vérifier si la DB tourne déjà avec des données
DB_HAS_DATA=$(docker exec smarthub-db psql -U smarthub -d smarthub -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" \
    2>/dev/null | tr -d ' ' || echo "0")

if [ "$DB_HAS_DATA" -gt "5" ]; then
    echo ""
    echo "⚠️  Base de données existante détectée ($DB_HAS_DATA tables)."
    echo "   → Application de la migration 002 (auth + interventions)..."
    docker exec -i smarthub-db psql -U smarthub -d smarthub < /srv/smarthub/db/002_auth_and_interventions.sql \
        2>/dev/null && echo "   ✅ Migration appliquée" \
        || echo "   ℹ️  Migration déjà appliquée ou erreur ignorée"
else
    echo ""
    echo "🆕 Nouvelle base de données — les deux scripts SQL seront exécutés au démarrage."
    docker compose down postgres
    docker compose up -d postgres
    echo "   Attente démarrage DB..."
    sleep 8
fi

# 5. Démarrer API
echo ""
echo "🚀 Démarrage API..."
docker compose up -d api

sleep 5
echo ""
echo "📋 Logs API (10 dernières lignes) :"
docker compose logs api --tail=10

# 6. Vérifier santé
echo ""
echo "🏥 Health check..."
sleep 3
HTTP=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health || echo "000")
if [ "$HTTP" = "200" ]; then
    echo "   ✅ API répond sur :8080 (HTTP $HTTP)"
else
    echo "   ❌ API ne répond pas (HTTP $HTTP) — vérifiez les logs"
    docker compose logs api --tail=20
    exit 1
fi

# 7. Vérifier si setup auth nécessaire
echo ""
echo "🔑 Vérification auth..."
SETUP=$(curl -s -X POST http://localhost:8080/api/v1/auth/setup \
    -H "Content-Type: application/json" || echo '{"error":"failed"}')

if echo "$SETUP" | grep -q "api_key"; then
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║          🎉 CLÉ API OWNER GÉNÉRÉE                   ║"
    echo "╠══════════════════════════════════════════════════════╣"
    API_KEY=$(echo "$SETUP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('api_key',''))")
    echo "║  $API_KEY"
    echo "╠══════════════════════════════════════════════════════╣"
    echo "║  ⚠️  COPIEZ CETTE CLÉ — elle ne sera plus affichée  ║"
    echo "║  Ajoutez-la dans le Qt :                            ║"
    echo "║  smarthub/api.py → API_KEY = \"<votre clé>\"         ║"
    echo "╚══════════════════════════════════════════════════════╝"
elif echo "$SETUP" | grep -q "existent"; then
    echo "   ℹ️  Clés API déjà configurées — pas de setup nécessaire"
else
    echo "   ⚠️  Setup auth : $SETUP"
fi

echo ""
echo "============================================"
echo " ✅ Déploiement terminé"
echo "============================================"
echo ""
echo " API      : http://localhost:8080"
echo " Docs     : http://localhost:8080/docs"
echo " pgAdmin  : https://pgadmin.smartclick.be"
echo ""
