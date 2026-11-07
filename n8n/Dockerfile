# n8n com os workflows do projeto dentro da imagem: no Portainer não há bind mount de arquivo do
# repositório. Os workflows são importados e publicados a cada subida pelo start-h2d.sh.
# Imagem oficial pelo Docker Hub (o docker.n8n.io limita pedidos com erro 429).
FROM n8nio/n8n:2.32.5
COPY --chown=node:node n8n/workflows /home/node/h2d-workflows
COPY --chown=node:node --chmod=755 n8n/start-h2d.sh /home/node/start-h2d.sh
ENTRYPOINT ["tini", "--", "/home/node/start-h2d.sh"]
