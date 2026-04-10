FROM postgres:16-alpine

# Les deux fichiers SQL sont exécutés dans l'ordre au premier démarrage
COPY 001_schema.sql /docker-entrypoint-initdb.d/001_schema.sql
COPY 002_auth_and_interventions.sql /docker-entrypoint-initdb.d/002_auth_and_interventions.sql
COPY 003_planning.sql /docker-entrypoint-initdb.d/003_planning.sql
