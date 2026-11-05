# O contexto de build é a raiz do repositório, porque a imagem inclui infra/Caddyfile.
FROM node:22-slim AS build
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# Atrás do Caddy da VPS: fala HTTP na 8080, sem HTTPS próprio, e roda sem root.
FROM caddy:2-alpine AS prod
RUN adduser -D -u 10001 web
ENV XDG_DATA_HOME=/tmp/xdg-data \
    XDG_CONFIG_HOME=/tmp/xdg-config
COPY infra/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/dist /srv
USER web
EXPOSE 8080
