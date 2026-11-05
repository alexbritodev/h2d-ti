#!/usr/bin/env bash
# Roda na VPS, em /opt/h2d. Uso: infra/scripts/deploy.sh <tag-da-imagem>
#
# Ordem: baixa as imagens, sobe o banco, aplica as migrações, sobe o resto e confere /api/ready.
# Se a conferência falhar, volta as imagens para a versão anterior.
# Atenção: o rollback não desfaz migrações. Toda migração precisa funcionar também com o código
# da versão anterior (primeiro adicione, depois use, só então remova).
set -euo pipefail

tag="${1:?informe a tag da imagem}"
cd /opt/h2d

set -a
# shellcheck disable=SC1091
. ./.env
set +a

compose() { IMAGE_TAG="$1" docker compose --env-file .env -f infra/compose.prod.yaml "${@:2}"; }

ready() {
  for _ in $(seq 1 30); do
    # --resolve testa pelo Caddy de verdade, com o certificado do domínio, sem depender do DNS.
    if curl -fsS --max-time 5 --resolve "${H2D_DOMAIN}:443:127.0.0.1" "https://${H2D_DOMAIN}/api/ready" >/dev/null; then
      return 0
    fi
    sleep 5
  done
  return 1
}

previous="$(cat .deployed-tag 2>/dev/null || true)"

compose "$tag" pull
compose "$tag" up -d --wait db
compose "$tag" run --rm api alembic upgrade head
compose "$tag" up -d --wait

if ready; then
  echo "$tag" > .deployed-tag
  docker image prune -f >/dev/null
  echo "Deploy concluído: $tag"
  exit 0
fi

echo "ERRO: /api/ready não respondeu depois do deploy de $tag." >&2
if [ -n "$previous" ]; then
  echo "Voltando para $previous..." >&2
  compose "$previous" up -d --wait
  ready && echo "Versão $previous restaurada." >&2
fi
exit 1
