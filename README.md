# H2D - TI

Central de atendimento de TI em que um assistente com IA resolve o que os manuais já respondem e só abre chamado, já classificado e atribuído a um técnico, quando a resolução automática falha.

**Entrega: 18/11/2026.**

## Estado atual

| Fase | Situação |
| --- | --- |
| F1 Fundação | No ar em **<https://h2d-ti.tech>** (VPS, stack do Portainer, HTTPS no Caddy). Faltam fechar os critérios de saída (#13) |
| F2 Ingestão | Pronta: envio de manuais, fila com worker, embeddings locais, busca híbrida com permissão e telas de Documentos e Base de conhecimento. Lê Markdown, texto, PDF e DOCX (PDF digitalizado, só imagem, não: não há OCR) |
| F3 Chat | Pronta: assistente com fontes citadas, mascaramento de dados sensíveis, limites e o modelo do OpenRouter |
| F4 Chamados | Pronta: classificação, prioridade, SLA, roteador, triagem manual, telas e avisos por e-mail via n8n (SMTP configurado na VPS) |
| F5 Automações | Pronta: vigia de SLA (alertas de 75% e 100%, uma vez cada), workflow de erro global e poda do histórico do n8n |
| F6 Dashboard | Pronta: defleção do assistente, custo por conversa, volume e SLA cumprido, com números reais conferidos por SQL |
| F7 Endurecimento e demo | Não começou: backup com restauração testada, CSP/HSTS e limite de requisições, teste e2e, avaliação do RAG e ensaio da demo |
| F8 Pendências | **Darles e Hanover:** itens que ficaram para trás nas fases F0 a F6 (decisões, avaliação do assistente, testes na VPS e segurança). Lista completa na seção F8 do [TODO](docs/TODO.md) |

Também pronto, fora das fases: **convite de usuário por e-mail** (link de uso único para a pessoa definir a própria senha) e **domínio definitivo**.

O detalhe item por item está no [TODO](docs/TODO.md).

## Acesso para avaliadores

Para testar o sistema em produção (**<https://h2d-ti.tech>**) com acesso completo (Assistente, Chamados, Documentos, Dashboard e Fluxo do RAG):

| Campo | Valor |
| --- | --- |
| Endereço | <https://h2d-ti.tech> |
| E-mail | `avaliador@h2d.local` |
| Senha | `Avaliador2026` |
| Papel | Administrador |

> **Observação (VPS/Portainer):** caso esta conta ainda não tenha sido criada no banco de produção, execute uma única vez no console do container `h2d-api`:
>
> ```bash
> ADMIN_EMAIL=avaliador@h2d.local ADMIN_NAME="Avaliador H2D" ADMIN_PASSWORD='Avaliador2026' python -m h2d.create_admin
> ```
>
> Para testes locais (`http://localhost:5173`), rode `docker compose exec api python -m h2d.seed` e utilize as contas listadas na seção [Como rodar](#como-rodar).

## O que o sistema faz

- **Base de conhecimento:** o administrador envia manuais (`.md`, `.txt`, `.pdf` ou `.docx`) em *Administração → Documentos*. Um worker divide o texto por títulos, gera os vetores e publica a versão de uma vez só. Arquivo repetido não é reprocessado, e a versão anterior só sai depois da nova estar pronta.
- **Permissão:** cada documento é público ou restrito à TI. Usuário comum nunca recebe trecho restrito, nem na busca, nem no chat, nem na biblioteca (o filtro roda dentro do SQL e tem teste automatizado).
- **Assistente e Agentes Inteligentes:** fluxo com dois agentes dedicados (Guardião de Entrada e Validador de Resposta) que filtram ofensas antes da LLM e barram alucinações antes de responder ao usuário, com visualização do progresso em tempo real no chat.
- **Dados sensíveis:** senha, CPF, cartão e token são escondidos antes de qualquer gravação, log ou envio ao modelo.
- **Chamados:** a conversa vira chamado com categoria, impacto e urgência sugeridos pelo modelo. A **prioridade sai de uma matriz em código**, o prazo de SLA é calculado em código e o técnico é escolhido por regras (habilidade, horário, capacidade e menor carga). Sem confiança ou sem técnico elegível, vai para a **triagem manual**. O motivo de cada atribuição fica na linha do tempo.
- **Papéis:** usuário (vê os próprios chamados), técnico (atende os que lhe cabem) e administrador (cadastros, ingestão, reatribuição).
- **Convite de usuário:** o administrador informa nome, e-mail e papel; a pessoa recebe um e-mail (no tema do app) com um link para definir a própria senha. O link vale 48 horas (configurável, mínimo 24), só funciona uma vez e pode ser reenviado (o anterior deixa de valer). A conta nasce sem senha utilizável, e no banco fica só o hash do token.
- **Dashboard:** defleção do assistente, custo por conversa, volume por dia e SLA cumprido, em números reais do banco (técnico e administrador). Cada número tem definição fixa e teste contra SQL escrito à mão.

## Pipeline de Agentes Inteligentes do Chat

O chat opera com um pipeline encadeado de proteção e auditoria de respostas, com emissão de eventos em tempo real via Server-Sent Events (SSE) para o frontend:

```text
Mensagem do Usuário
       │
       ▼
[Agente 1: Guardião de Entrada] ────(Reprovado)───► Resposta educada de recusa (Sem RAG / Sem LLM)
       │ (Aprovado)
       ▼
[Recuperação RAG nos Manuais] ──────(Vazio)───────► Informa ausência nos manuais (Sem LLM)
       │ (Trechos encontrados)
       ▼
[Geração da Resposta pela LLM]
       │
       ▼
[Agente 2: Validador de Resposta] ──(Inválida)────► Regeneração restritiva única
       │ (Válida)                                         │
       │                                            (Reprovada de novo)
       ▼                                                  ▼
Resposta final ao colaborador                  Oferece chamado à equipe técnica
```

### Agente 1: Guardião de Entrada (Filtro de Conteúdo)
- **Localização:** `apps/api/src/h2d/agents/guardiao.py` e `guardiao_terms.json`.
- **Estratégia em duas camadas:**
  1. *Camada rápida:* normalização de acentos, desofuscação de leet speak (`p0rr4` -> `porra`), colapso de repetições exageradas (`poooorrrra` -> `porra`) e espaços artificiais (`p o r r a` -> `porra`), com proteção ativa para termos técnicos de TI (`kill process`, `master/slave`, `abortar`, `dump`).
  2. *Camada semântica:* chamada à LLM quando a camada rápida não detecta infrações explícitas, identificando ironia, ódio velado ou assédio sutil.
- **Ação em reprovação:** bloqueia a execução imediatamente, sem acionar o RAG nem a LLM de geração, devolvendo uma recusa educada ao colaborador.

### Agente 2: Validador de Resposta (Anti-alucinação)
- **Localização:** `apps/api/src/h2d/agents/validador.py`.
- **Auditoria de 4 critérios:** sustentação fática pelos manuais, ausência de instruções inventadas, pertinência à pergunta e não-contradição com a base.
- **Decisão:** avalia o índice de confiança retornado em JSON estrito pelo juiz. Se reprovada, aciona **uma tentativa de regeneração restritiva**. Se ainda assim não constar na base, informa com segurança a ausência e sugere abertura de chamado técnico.

### Visualização do Progresso em Tempo Real (Painel de Agentes)
- **Componente:** `apps/web/src/features/chat/AgentProgressPanel.tsx`.
- **Streaming SSE:** eventos `agent_progress` emitidos instantaneamente pelo backend:
  `{ agente: "guardiao"|"rag"|"llm"|"validador", status: "aguardando"|"em_andamento"|"aprovado"|"reprovado"|"erro", mensagem: string, detalhes?: object, timestamp: string }`
- **Interface:** timeline/stepper responsivo com status visual animado (spinner em andamento, check verde, alerta/X vermelho), exibição clara do motivo de eventuais bloqueios e detalhes técnicos expansíveis (confiança, categoria, manuais usados), permanecendo recolhível para consulta após o término da resposta.

### Variáveis de Ambiente dos Agentes (.env)

```bash
# Liga/desliga cada agente de forma independente
GUARDIAO_ENABLED=true
GUARDIAO_FAST_ONLY=false
GUARDIAO_MODEL=openrouter/free

VALIDADOR_ENABLED=true
VALIDADOR_MODEL=openrouter/free
VALIDADOR_CONFIDENCE_THRESHOLD=0.7
```

## Documentos

- [Plano do projeto](docs/H2D-TI-plano.md): visão, arquitetura, stack e regras de negócio
- [Plano de implementação](docs/PLANO-IMPLEMENTACAO.md): fases, calendário, cortes e riscos
- [Todo list](docs/TODO.md): tarefas por fase e critérios de saída
- [Decisões de arquitetura](docs/adr/): Python no backend, divergências do plano e embeddings
- [Modelo de dados](docs/MODELO-DADOS.md)
- [Runbook da VPS e do deploy](docs/RUNBOOK-VPS.md)

## Como rodar

Só é preciso ter o Docker e o Git.

1. Copie o arquivo de ambiente e troque todos os valores `troque-me`:

   ```bash
   cp .env.example .env
   ```

   Para usar o assistente de verdade, acrescente no `.env` a linha `OPENROUTER_API_KEY=` com a sua chave (o arquivo é ignorado pelo Git). Sem a chave o sistema sobe normalmente, mas o assistente responde que está indisponível.

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

5. Para testar o assistente, entre como admin, abra *Administração → Documentos* e envie manuais em Markdown. A primeira busca baixa o modelo de embeddings (cerca de 220 MB) e demora um pouco.

| Serviço | Endereço | Observação |
| --- | --- | --- |
| Frontend | <http://localhost:5173> | Recarrega sozinho ao editar |
| API | <http://localhost:8010/api/docs> | Muda com `API_PORT` |
| Banco | `localhost:5433` | Muda com `DB_PORT` |
| Worker | sem porta | Processa a fila de ingestão |

Se uma porta estiver ocupada, troque-a no `.env`. O ambiente local tem o banco `h2d` e o banco `h2d_test`, exclusivo dos testes.

**Dois arquivos de compose.** `compose.dev.yaml` é o ambiente de desenvolvimento e `docker-compose.yml` é o stack de produção do Portainer. O `.env.example` traz a linha `COMPOSE_FILE=compose.dev.yaml`, que faz o `docker compose` local usar o de desenvolvimento sem você digitar `-f`. Sem essa linha (por exemplo, num servidor), o Compose usa o de produção.

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

**Testes dos Agentes (Guardião, Validador e Pipeline):**

```bash
# Backend (Guardião, Validador e Pipeline de integração):
uv --directory apps/api run pytest tests/test_guardiao.py tests/test_validador.py tests/test_agents_pipeline.py -v

# Frontend (Painel de visualização em tempo real):
npm.cmd --prefix apps/web test src/features/chat/AgentProgressPanel.test.tsx
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

**Criar uma migração** depois de alterar `models.py`. Revise o arquivo gerado (principalmente tipos enum) e confira com `alembic check`:

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

Se você adicionar uma dependência ao front, reinicie o container para instalar: `docker compose restart web`.

**Ativar os hooks de commit** (gitleaks e ruff). Exige o [uv](https://docs.astral.sh/uv/):

```bash
uvx pre-commit install
```

## Estrutura

| Pasta | Conteúdo |
| --- | --- |
| `apps/api` | FastAPI, SQLAlchemy, Alembic. `kb/` é a ingestão e a busca, `chat/` o assistente, `tickets/` as regras de chamado, `llm/` o cliente do modelo |
| `apps/web` | React, Vite, TanStack Router e Query, Tailwind. Uma pasta por área em `src/features/` |
| `infra` | Caddyfile do container web, scripts do banco e o desenho antigo de deploy por SSH (sem uso) |
| `docs` | Plano, ADRs, modelo de dados, runbook e TODO |
| `manuais` | Manuais fictícios para testar a base. **Não vai para o Git**: ficam só na máquina |
| `n8n` | Workflows exportados (aviso de chamado e convite, vigia de SLA, erro global) e a imagem que os leva |

## Deploy

O sistema roda em <https://h2d-ti.tech>, na VPS, como um stack do Portainer que compila direto deste repositório (`docker-compose.yml`), atrás do Caddy da VPS (que emite o HTTPS; o DNS aponta `@` para a VPS). As variáveis e segredos ficam só no Portainer. O passo a passo, as armadilhas já encontradas e a atualização estão no [runbook](docs/RUNBOOK-VPS.md).

## Como contribuir

Até a proteção da `main` estar definida, vale a convenção: nada de push direto na `main`, sempre por PR. As regras completas estão na seção 10 do plano do projeto.

Nunca commite `.env`, chaves, dumps de banco ou os manuais de teste.
