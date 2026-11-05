# Atalhos para o Docker Compose. Sem make (comum no Windows), rode os mesmos comandos
# diretamente; todos estão no README.
.PHONY: dev down logs seed migrate check check-api check-web contract

dev:
	docker compose up -d --wait

down:
	docker compose down

logs:
	docker compose logs -f

seed:
	docker compose exec api python -m h2d.seed

migrate:
	docker compose exec api alembic upgrade head

check: check-api check-web contract

check-api:
	docker compose exec api ruff format --check .
	docker compose exec api ruff check .
	docker compose exec api pyright
	docker compose exec api pytest -q

check-web:
	docker compose exec web npm run lint
	docker compose exec web npm run typecheck
	docker compose exec web npm test

# Regenera o contrato e o cliente TypeScript. Commite o resultado.
contract:
	docker compose exec api python -m h2d.export_openapi openapi.json
	docker compose exec web npm run gen:api
