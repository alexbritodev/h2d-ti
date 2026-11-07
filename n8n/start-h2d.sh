#!/bin/sh
# Importa e publica os workflows do H2D a cada subida do n8n, e só então inicia o n8n.
# Falha aqui nunca impede o n8n de subir: o erro aparece no log do container.
for step in "import:workflow --separate --input=/home/node/h2d-workflows" \
  "publish:workflow --id=h2d-erro-global" \
  "publish:workflow --id=h2d-aviso-chamado" \
  "publish:workflow --id=h2d-vigia-sla"; do
  # shellcheck disable=SC2086
  n8n $step || echo "[h2d] falhou: n8n $step"
done
exec /docker-entrypoint.sh "$@"
