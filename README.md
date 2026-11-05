# H2D - TI

Central de atendimento de TI em que um chatbot com RAG resolve o que os manuais já respondem e só abre chamado, já classificado e atribuído a um técnico, quando a resolução automática falha.

**Entrega: 18/11/2026.** Estado atual: fase F1, com login e ambiente local funcionando.

## Documentos

- [Plano do projeto](docs/H2D-TI-plano.md): visão, arquitetura, stack e regras de negócio
- [Plano de implementação](docs/PLANO-IMPLEMENTACAO.md): fases, calendário, cortes e riscos
- [Todo list](docs/TODO.md): tarefas por fase e critérios de saída
- [Decisões de arquitetura](docs/adr/)
- [Modelo de dados](docs/MODELO-DADOS.md)
- [Runbook da VPS e do deploy](docs/RUNBOOK-VPS.md)

## Como rodar

Só é preciso ter o Docker e o Git.

1. Copie o arquivo de ambiente e troque todos os valores `troque-me`:

   ```bash
   cp .env.example .env
   ```

2. Suba o ambiente. Na primeira vez leva alguns minutos:

   ```bash
   docker compose up -d --wait
   ```

3. Crie os dados de demonstração:

   ```bash
   docker compose exec api python -m h2d.seed
   ```

4. Abra <http://localhost:5173> e entre com a senha definida em `SEED_PASSWORD`:

   | Papel | E-mail |
   | --- | --- |
   | Admin | `admin@h2d.local` |
   | Técnico | `tecnico1@h2d.local` a `tecnico3@h2d.local` |
   | Usuário | `usuario1@h2d.local` a `usuario3@h2d.local` |

| Serviço | Endereço | Observação |
| --- | --- | --- |
| Frontend | <http://localhost:5173> | Recarrega sozinho ao editar |
| API | <http://localhost:8010/api/docs> | Muda com `API_PORT` |
| Banco | `localhost:5433` | Muda com `DB_PORT` |

Se uma porta estiver ocupada, troque-a no `.env`. O ambiente local tem o banco `h2d` e o banco `h2d_test`, exclusivo dos testes.

## Comandos do dia a dia

Com `make`, use `make check` e `make contract`. Sem `make`, comum no Windows, rode os comandos abaixo.

**Verificar o backend:**

```bash
docker compose exec api ruff format --check .
```

```bash
docker compose exec api ruff check .
```

```bash
docker compose exec api pyright
```

```bash
docker compose exec api pytest -q
```

**Verificar o frontend:**

```bash
docker compose exec web npm run lint
```

```bash
docker compose exec web npm run typecheck
```

```bash
docker compose exec web npm test
```

**Criar uma migração** depois de alterar `models.py`. Revise o arquivo gerado antes de commitar:

```bash
docker compose exec api alembic revision --autogenerate -m "descricao"
```

**Regenerar o contrato** quando a API mudar. O CI falha se o resultado não for commitado:

```bash
docker compose exec api python -m h2d.export_openapi openapi.json
```

```bash
docker compose exec web npm run gen:api
```

**Ativar os hooks de commit** (gitleaks e ruff). Exige o [uv](https://docs.astral.sh/uv/):

```bash
uvx pre-commit install
```

## Como contribuir

Até a proteção da `main` estar definida, vale a convenção: nada de push direto na `main`, sempre por PR. As regras completas estão na seção 10 do plano do projeto.

Nunca commite `.env`, chaves ou dumps de banco.
