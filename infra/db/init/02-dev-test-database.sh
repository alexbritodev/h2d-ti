#!/bin/sh
# Somente desenvolvimento: banco separado para o pytest. Não é montado em produção.
set -eu

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres <<'SQL'
CREATE DATABASE h2d_test OWNER h2d;
SQL

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d h2d_test <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
