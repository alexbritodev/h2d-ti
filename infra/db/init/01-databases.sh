#!/bin/sh
# Roda só na primeira criação do volume do banco.
# Cria os bancos h2d e n8n com usuários separados, sem acesso cruzado.
set -eu

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres \
  -v h2d_password="$H2D_DB_PASSWORD" \
  -v n8n_password="$N8N_DB_PASSWORD" <<'SQL'
CREATE ROLE h2d LOGIN PASSWORD :'h2d_password';
CREATE ROLE n8n LOGIN PASSWORD :'n8n_password';
CREATE DATABASE h2d OWNER h2d;
CREATE DATABASE n8n OWNER n8n;
REVOKE CONNECT ON DATABASE h2d FROM PUBLIC;
REVOKE CONNECT ON DATABASE n8n FROM PUBLIC;
SQL

# A extensão vector exige superusuário; pg_trgm fica junto para manter tudo em um lugar.
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d h2d <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
