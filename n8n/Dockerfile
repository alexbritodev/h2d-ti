# n8n com os workflows do projeto dentro da imagem: no Portainer não há bind mount de arquivo do
# repositório. Importe com: n8n import:workflow --separate --input=/home/node/h2d-workflows
# Imagem oficial pelo Docker Hub (o docker.n8n.io limita pedidos com erro 429).
FROM n8nio/n8n:2.32.5
COPY --chown=node:node n8n/workflows /home/node/h2d-workflows
