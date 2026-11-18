# H2D - TI: Stacks do Projeto e Roteiro de Apresentação

**Data da entrega:** 18/11/2026  
**Ambiente no ar:** <https://h2d-ti.tech>  
**Documentos relacionados:** [README](../README.md) · [Plano do Projeto](H2D-TI-plano.md) · [Plano de Implementação](PLANO-IMPLEMENTACAO.md) · [TODO](TODO.md) · [Modelo de Dados](MODELO-DADOS.md) · [Runbook VPS](RUNBOOK-VPS.md) · [Escritório Virtual](escritorio-virtual.md)

---

## Parte 1 — As Stacks do Projeto (Planejado vs. Implementado na Prática)

O **H2D - TI** é uma central de atendimento de TI com assistente RAG (*Retrieval-Augmented Generation*), triagem inteligente e roteamento automático de chamados. Toda a arquitetura foi desenhada para rodar **em containers Docker numa única VPS (Hostinger KVM 2)** com custo mínimo de operação, alta previsibilidade e entrega em 14 dias (04/11 a 18/11/2026).

### Visão Geral da Arquitetura em Produção

```mermaid
flowchart TB
  NAV["Navegador (React 19 + TypeScript SPA)"] --> CADDY["Caddy da VPS (HTTPS automático / Proxy)"]
  CADDY -->|"/" e "/api/*"| WEB["h2d-web (SPA estática + Caddy interno :8080)"]
  WEB -->|"/api/*"| API["h2d-api (FastAPI + Uvicorn :8000)"]
  CADDY -.->|"Bloqueia /api/hooks/* (404/403 externo)"| API
  API <--> DB[("h2d-db: PostgreSQL 17 + pgvector\n(bancos h2d e n8n)")]
  API -->|"OpenRouter API"| LLM["LLM (openrouter/free + fallbacks)"]
  WORKER["h2d-worker (Ingestion + Outbox)"] <--> DB
  WORKER -->|"Embeddings locais (FastEmbed ONNX)"| WORKER
  WORKER -->|"Webhooks assinados (HMAC-SHA256)"| N8N["h2d-n8n (:5678, rede interna)"]
  N8N -->|"Endpoints assinados (/api/hooks/n8n/*)"| API
  N8N <--> DB
  N8N -->|"SMTP"| MAIL["E-mails (chamados, SLA e convites)"]
```

> **Decisão-chave de arquitetura ([ADR-002](adr/0002-divergencias-do-plano.md)):** O `n8n` e o banco PostgreSQL nunca ficam expostos à internet no MVP. Toda comunicação entre API, Worker e n8n trafega pela rede interna `interna` do Docker com assinatura **HMAC-SHA256** nos dois sentidos, enquanto o Caddy da VPS expõe apenas HTTPS (`h2d-ti.tech`) e bloqueia `/api/hooks/*` de fora.

---

### Resumo das Escolhas: Planejado vs. Realidade em Produção

Durante as 2 semanas de desenvolvimento, o time tomou decisões pragmáticas (documentadas nos ADRs) para cortar peso de memória na VPS e evitar complexidade desnecessária mantendo 100% da confiabilidade:

| Camada | Planejado Inicialmente | Implementado em Produção | Por que mudou? |
| --- | --- | --- | --- |
| **Parsing de documentos** | Docling | `h2d.kb.parsing` (`pypdf`, `python-docx` e Markdown/texto) | O Docling estourava a memória RAM da VPS (KVM 2, 7,8 GB sem swap). A extração leve reconhece títulos, listas e tabelas, limpa cabeçalhos/rodapés e recusa PDF escaneado sem OCR. |
| **Orquestração do chat** | LangGraph + checkpointer | Pipeline direto em funções Python (`h2d/chat/service.py`) | Fluxo mais simples, rápido, fácil de testar e sem tabelas extras fora do Alembic. |
| **Fila assíncrona** | Procrastinate | Tabela `ingestion_jobs` + `outbox_events` com `SELECT ... FOR UPDATE SKIP LOCKED` | Zero dependências extras de fila; o histórico e os motivos de falha ficam na mesma tabela que a UI consulta. |
| **Embeddings** | BGE-M3 / multilingual-e5-large | `paraphrase-multilingual-MiniLM-L12-v2` (384d, **FastEmbed local**) | Único que cabe com folga na VPS (~1,2 GB RAM residente vs. ~3,8 GB do e5-large), com busca híbrida compensando termos exatos ([ADR-003](adr/0003-embeddings.md)). |
| **UI Components** | `shadcn/ui` CLI | Primitivas **Radix UI** + componentes próprios + Tailwind v4 | Evita o CLI sobrescrevendo arquivos e mantém tema claro/escuro de ERP moderno com contraste validado ([ADR-002 D10/D11](adr/0002-divergencias-do-plano.md)). |
| **Deploy** | GitHub Actions → GHCR → SSH | **Portainer Stack** (`docker-compose.yml`) com build direto do Git | Menos peças móveis na VPS, variáveis isoladas no Portainer e atualização via *Pull and redeploy* ([Runbook](RUNBOOK-VPS.md)). |

---

### 1. Frontend (`apps/web`) — SPA Moderna, Leve e Tipada

A interface foi construída como uma **Single Page Application (SPA)** estática servida com apenas `128m` de `mem_limit` em produção (`h2d-web`), pois área logada de ERP não precisa de SSR/SEO.

- **Núcleo:** `React 19.3`, `TypeScript 5.9` e `Vite 8`.
- **Roteamento e Cache de Dados:** `TanStack Router` (rotas protegidas por papel `user`, `tech`, `admin`) + `TanStack Query v5`.
- **Estilização e Design System:**
  - `Tailwind CSS v4` + `Radix UI` (primitivas acessíveis) + componentes próprios (`DataTable`, `KpiTile`, `CitationCard`, `ChatStream`, `StatusTag`).
  - Paleta de comandos `cmdk` (`Ctrl+K`), ícones `lucide-react`.
  - Tipografia: `Geist` para interface e `JetBrains Mono` para códigos, IDs e comandos (`tokens.css`, tema claro por padrão e escuro opcional).
- **Formulários e Renderização:** `react-hook-form` + `zod` v4 para validação; `react-markdown` + `remark-gfm` para formatar respostas, listas e blocos de código copiáveis do assistente.
- **Contrato Tipado Fim a Fim (API ↔ Front):** `openapi-typescript` + `openapi-fetch` geram `src/lib/api/schema.d.ts` diretamente do `apps/api/openapi.json` exportado pelo FastAPI. Se o backend mudar e o front não regenerar os tipos, **o CI quebra**.
- **Tempo Real:** Server-Sent Events (**SSE**) via `fetch` stream no chat (necessário porque a mensagem é enviada via `POST`) e `EventSource` nativo com reconexão automática (`Last-Event-ID`) no Escritório Virtual.

---

### 2. Backend & Worker (`apps/api`) — Python Assíncrono e Contrato Estrito

A escolha por Python ([ADR-001](adr/0001-python-no-backend.md)) unificou API, parsing de documentos, embeddings locais e lógica de IA no mesmo código, sem precisar subir microsserviços separados.

- **Núcleo Web:** `Python 3.12`, `FastAPI`, `Uvicorn` e `Pydantic v2` (`pydantic-settings`), gerenciados com `uv`.
- **Persistência:** `SQLAlchemy 2` assíncrono (`asyncpg`) + `Alembic` (migrações idempotentes executadas automaticamente na subida da API antes do Uvicorn). Chaves primárias em **UUID v7** geradas na aplicação (`uuid-utils`), já que o PostgreSQL 17 não possui `uuidv7()` nativo.
- **Autenticação, Sessão e Convites:**
  - JWT (`PyJWT`) armazenado em **cookie `httpOnly`** (`Secure` em produção, `SameSite=Lax`), protegendo contra XSS.
  - Hash de senhas com **Argon2** (`argon2-cffi`).
  - Controle de acesso baseado em papéis (**RBAC**): `user` (usuário final), `tech` (técnico de TI) e `admin` (administrador).
  - **Convite por e-mail:** conta nasce sem senha utilizável; token de uso único (validade configurável, padrão 48h) guardado como hash no banco; reenvio invalida o link anterior.
- **Worker Dedicado (`h2d-worker`):**
  - Usa a **mesma imagem Docker da API** (`h2d-api:prod`), rodando `python -m h2d.worker`.
  - Consome duas filas diretamente no PostgreSQL:
    1. **Ingestão (`ingestion_jobs`)** com `SKIP LOCKED` e recuperação automática de jobs travados (`requeue_stale`).
    2. **Outbox (`outbox_events`)** para entregar eventos ao `n8n` com backoff exponencial (até 10 tentativas) e garantia de entrega mesmo se o `n8n` cair.

---

### 3. Banco de Dados & Busca Híbrida (`h2d-db`)

Um único servidor **PostgreSQL 17** (`pgvector/pgvector:pg17`) centraliza dados relacionais, vetores, busca textual e filas:

- **Isolamento de Bancos:** `h2d` (aplicação), `n8n` (workflows e execuções) e `h2d_test` (testes automatizados em dev/CI), com usuários e credenciais separados.
- **Busca Híbrida com RRF (Reciprocal Rank Fusion):**
  - **Busca Semântica:** coluna `embedding vector(384)` indexada com **HNSW** (`vector_cosine_ops`) e `hnsw.iterative_scan` ativado — essencial para que filtros por permissão não devolvam menos resultados que o esperado.
  - **Busca Lexical:** `tsvector` configurado para português (`portuguese`) + `pg_trgm`, cobrindo códigos de erro, comandos (`systemctl --failed`, `ipconfig /flushdns`) e números exatos (`90 dias`, `25 MB`) onde modelos pequenos de embedding são mais fracos.
  - **Fusão:** os candidatos vetoriais e textuais são combinados via **RRF diretamente em SQL**, sem precisar manter Elasticsearch/Qdrant na VPS.
- **Segurança no SQL:** A visibilidade do documento (`publico` vs. `ti`) é copiada para cada linha de `kb_chunks` e filtrada **dentro da consulta SQL**. Um usuário comum nunca recebe trecho restrito à TI — nem na busca, nem no chat, nem na biblioteca.

---

### 4. IA, RAG, Triagem Híbrida e Guardrails

A inteligência do sistema foi desenhada sob o princípio: **IA para linguagem e sugestão; código determinístico para regras de negócio e segurança**.

- **Embeddings 100% Locais ([ADR-003](adr/0003-embeddings.md)):**
  - `FastEmbed` rodando em CPU (ONNX) com `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões).
  - Vantagens: zero latência de rede para embutir documentos/perguntas, custo zero de API de embeddings, nenhum manual interno sai da VPS na indexação e ~1,2 GB de RAM residente.
  - Cada chunk registra `embedding_model` para evitar mistura de vetores e permitir reindexação controlada; a publicação de novas versões de documento é **atômica** (versão anterior só é arquivada após a nova estar pronta) e arquivos idênticos são ignorados via **hash SHA-256**.
- **Pipeline do Assistente (`h2d/chat/service.py`):**
  1. **Mascaramento imediato (`h2d/chat/masking.py`):** detecta e mascara senhas (`senha: ...`), CPFs (com validação de dígitos), números de cartão (validação Luhn) e tokens/chaves (`Bearer`, `eyJ...`, `sk-`, `ghp_`, `AKIA...`) *antes* de gravar no banco, gerar log ou enviar ao LLM.
  2. **Limites de proteção:** limite de turnos, tamanho da mensagem e teto diário global de requisições ao LLM (`LLM_DAILY_REQUEST_LIMIT`, padrão 45 para o plano gratuito).
  3. **Reescrita e Busca Híbrida:** reescreve a pergunta considerando o histórico recente, busca os trechos permitidos e expande seções relevantes.
  4. **Geração delimitada + Citação obrigatória:** os trechos entram delimitados como dado (proteção contra *prompt injection* embutido em documentos) e o modelo só responde com base neles, citando a fonte.
  5. **Checagem de fidelidade e Escalonamento:** verifica se a resposta está sustentada pelos trechos. Se não houver base, o tema for crítico ou o usuário pedir humano, oferece/inicia a abertura de chamado.
- **Cliente LLM Desacoplado (`h2d/llm/client.py`):**
  - Cliente HTTP fino (`httpx`) apontando para o **OpenRouter** (`OPENROUTER_MODEL=openrouter/free` por padrão, com lista de `OPENROUTER_FALLBACK_MODELS`).
  - `FakeLLM` para desenvolvimento local e testes automatizados sem gastar cota nem depender de chave.
  - Observabilidade financeira: todas as chamadas gravam modelo, `prompt_versions`, tokens de entrada/saída, latência e custo na tabela `llm_calls`.
- **Triagem Híbrida (LLM + Regras em Código em `h2d/tickets/rules.py`):**
  - **O que o LLM faz:** gera saída estruturada (validada por **Pydantic**) sugerindo `categoria`, `subcategoria`, `impacto`, `urgencia`, `resumo`, `ja_tentado`, `habilidades` e `confianca`.
  - **O que o Código faz (100% testável e auditável):**
    - **Prioridade (P1 a P4):** calculada exclusivamente pela matriz `Impacto × Urgência` em código (`priority_from`), nunca inventada pelo modelo.
    - **Prazo de SLA:** calculado em código (`sla_due`, estado `at_risk` a partir de 75% e `breached` em 100%).
    - **Roteador de Atribuição (`route`):** sem LLM — filtra técnicos ativos com a habilidade necessária, dentro do horário da agenda (`in_schedule`) e abaixo da capacidade máxima, escolhendo quem tem menor carga ponderada (`P1=8, P2=4, P3=2, P4=1`) e desempatando por rodízio (`last_assigned_at`). Sem confiança mínima ou sem técnico elegível, encaminha para a **fila de triagem manual** e grava o motivo exato em `ticket_events`.
    - **Resiliência (Plano B):** se o OpenRouter cair ou estourar cota, o chamado é aberto mesmo assim sem classificação automática para nunca travar o atendimento.

---

### 5. Automações e Notificações (`h2d-n8n`)

- **n8n self-hosted (`2.32.5`)** com banco PostgreSQL dedicado (`n8n`), imagem customizada (`n8n/Dockerfile`) que já carrega e publica os workflows no startup (`n8n/start-h2d.sh`), e poda automática de histórico (mantém apenas execuções com erro por 7 dias).
- **Workflows versionados em JSON (`n8n/workflows/`):**
  1. `01-aviso-de-chamado.json`: envia e-mails de chamado criado/atribuído/resolvido, alertas de SLA e convites de usuário (P1 notifica também o líder de TI). Possui deduplicação pelos últimos 500 `event_id` recebidos.
  2. `02-vigia-de-sla.json`: executa a cada 5 minutos chamando `POST /api/hooks/n8n/sla-check` (assinado com HMAC); a API gera alertas únicos ao atingir **75%** e **100%** do SLA e enfileira no outbox.
  3. `05-erro-global.json`: qualquer falha em outro workflow notifica o e-mail do líder com nome do workflow, nó e erro.
- **Ambiente Local:** perfil `n8n` do `compose.dev.yaml` sobe junto o **Mailpit** (`http://localhost:8025`) para testar todos os e-mails localmente sem disparar nada para a rua.

---

### 6. Infraestrutura, CI/CD e Qualidade

- **Hospedagem e Proxy:** VPS Hostinger (KVM 2, Ubuntu 24.04), domínio `https://h2d-ti.tech`, proxy reverso e TLS automático via **Caddy**, orquestração pelo **Portainer** via `docker-compose.yml`.
- **Pipeline de CI (`.github/workflows/ci.yml` — 5 jobs automáticos):**
  1. **Backend:** `ruff format --check`, `ruff check`, `pyright`, `pytest` contra container real de `pgvector/pgvector:pg17`.
  2. **Frontend:** `eslint`, `tsc --noEmit`, `vitest`, `vite build`.
  3. **Contrato da API:** gera `openapi.json` + `schema.d.ts` e falha o build se houver divergência não commitada.
  4. **Segurança:** `gitleaks` (histórico de segredos), `pip-audit`, `npm audit`.
  5. **Imagens & Vulnerabilidades:** build das imagens `prod` de API e Web + varredura **Trivy** (`CRITICAL,HIGH`).
- **Pré-commit local:** `.pre-commit-config.yaml` com `gitleaks` e `ruff`.

---

### 7. Diferencial Visual: Escritório Virtual ([`docs/escritorio-virtual.md`](escritorio-virtual.md))

- Experimento isolado por feature flag (`ESCRITORIO_VIRTUAL_ENABLED=true`, com aba opcional `ESCRITORIO_VIRTUAL_DEMO=true`) que renderiza em **pixel art isométrico** os agentes percorrendo 6 salas conforme eventos reais da tabela `agent_events`:
  1. **Recepção** (`mensagem_recebida` / `resposta_enviada`)
  2. **Base de Conhecimento / RAG** (`rag_busca`)
  3. **Triagem** (`classificado` / `triagem_manual`)
  4. **Banco de Dados** (`sql_leitura`)
  5. **Técnicos de TI** (`chamado_criado`, `chamado_atribuido`)
  6. **Auditoria** (`evento_registrado`)
- Disponível em tela cheia (`/escritorio`, com modos **Ao vivo** via SSE, **Replay** passo a passo e **Demonstração**) e como **Mini-escritório flutuante** no canto inferior direito das demais telas, respeitando `prefers-reduced-motion` e acessibilidade (`role="log"`).

---
---

## Parte 2 — Roteiro para Montar a Apresentação de Hoje (18/11/2026)

> **Duração sugerida total:** 12 a 15 minutos (6 a 7 min de slides/arquitetura + 5 a 6 min de demonstração ao vivo + 2 min de encerramento/perguntas).  
> **Foco da narrativa:** Não é apenas "um chat conectado ao ChatGPT". É um **produto de engenharia completo em produção (`https://h2d-ti.tech`)**, com segurança no SQL, LGPD desde o dia 1, custo controlado, regras auditáveis e automação resiliente.

### Estrutura dos Slides (7 Slides Diretos)

#### Slide 1 — Capa e O Problema (1 min)
- **Título:** *H2D - TI: Central de Atendimento Inteligente com RAG e Triagem Automatizada*
- **Gancho de fala:** *"Toda equipe de TI perde horas por dia respondendo às mesmas perguntas — senha vencida, VPN que não abre sistema, limite de anexo. Os manuais existem, mas ninguém os encontra; quando o chamado chega ao técnico, vem sem contexto e sem prioridade definida."*
- **Visual sugerido:** 3 bullets do problema (Chamados repetitivos · Manuais ignorados · Triagem manual lenta) + link no ar `https://h2d-ti.tech`.

#### Slide 2 — A Solução e Proposta de Valor (1 min)
- **Fluxo em 1 frase:** O usuário conversa com o assistente → se os manuais respondem, o bot resolve com **citação obrigatória** (defleção) → se não resolve ou é incidente crítico, abre chamado **já resumido, classificado e roteado** para o técnico certo.
- **Visual sugerido:** Fluxograma simples em 4 blocos: `Pergunta → Busca nos Manuais (RAG) → Resolveu? (Defleção) | Não resolveu? (Classifica + Roteia + Notifica)`.

#### Slide 3 — Arquitetura e Stack Tecnológica (2 min)
- **Visual sugerido:** Diagrama da arquitetura (Caddy/HTTPS → React SPA → FastAPI + Worker → PostgreSQL 17 `pgvector` → OpenRouter + n8n).
- **3 destaques técnicos para falar (não leia listas de pacotes!):**
  1. **PostgreSQL 17 como "motor único":** dados relacionais, busca híbrida (vetor HNSW + `tsvector` em português fundidos por RRF) e filas transacionais (`SKIP LOCKED` + Outbox) no mesmo banco — zero Redis ou banco vetorial pago.
  2. **Embeddings locais em CPU (`FastEmbed`):** custo zero, privacidade dos manuais e apenas ~1,2 GB de RAM na VPS.
  3. **Contrato fechado API ↔ Front:** OpenAPI do FastAPI gera automaticamente os tipos TypeScript do React, validado no CI.

#### Slide 4 — Engenharia de Segurança, Guardrails e Triagem Híbrida (1,5 min)
- **Mensagem central:** *"IA onde ela é boa (linguagem); código determinístico onde precisa de auditoria e segurança."*
- **4 pilares para destacar:**
  1. **Permissão dentro do SQL:** documentos `publico` vs. `ti` filtrados direto na consulta do `pgvector` — usuário comum jamais recebe trecho restrito.
  2. **Guardrails & LGPD antes do LLM:** `mask_sensitive` remove senha, CPF, cartão e tokens antes de gravar no banco, gerar log ou chamar o OpenRouter; trechos são delimitados contra *prompt injection*.
  3. **Fidelidade e Citação:** checagem de fidelidade + botão para abrir o trecho exato da fonte; se não sabe, admite e oferece chamado (não alucina).
  4. **Triagem Híbrida:** LLM sugere categoria/impacto/urgência em JSON tipado (Pydantic); **prioridade (P1–P4), SLA e roteamento do técnico** rodam em código puro, gravando o motivo na linha do tempo.

#### Slide 5 — Transição para a Demonstração ao Vivo (5 a 6 min)
- **Slide simples:** *"Demonstração ao Vivo — https://h2d-ti.tech"* (ou só o logo/título dos 5 atos enquanto alterna para o navegador).

#### Slide 6 — Métricas, Avaliação e Qualidade (1,5 min)
- **O que mostrar do sistema:**
  - **Dashboard de Gestão:** Taxa de Defleção, Custo por Conversa (`llm_calls`), Volume diário e SLA cumprido (todos validados contra SQL manual em testes automatizados).
  - **Qualidade medida (Evaluation):**
    - *Busca RAG (ADR-003, 22 perguntas nos 15 manuais):* Top-5 atingiu **20/22** acertos com busca híbrida (MiniLM 384d local).
    - *Classificador (`eval/classificacao_v0.jsonl`, amostra calibrada de 12 conversas):* **11/12** de acerto em categoria, **10/12** em subcategoria, **8/12** em prioridade exata e **12/12** dentro da margem de 1 nível.
  - **CI/CD & Segurança:** 5 jobs no GitHub Actions (`ruff`, `pyright`, `pytest` c/ pgvector, `eslint`, `tsc`, `vitest`, diff de contrato OpenAPI, `gitleaks`, `pip-audit`, `npm audit` e `Trivy`).

#### Slide 7 — Decisões Pragmáticas, Escopo em 14 Dias e Fase 2 (1 min)
- **Como entregamos em 14 dias (04/11 a 18/11):**
  - Cortes conscientes de MVP documentados (ex.: troca do Docling por parser leve para caber na VPS; foco nos KPIs essenciais no dashboard; cadastros pré-carregados no seed + convite por e-mail).
- **Próximos passos (Pós-MVP / Fase 2):**
  - Fechar os testes de avaliação completa (30+ casos escritos por terceiros) e backup automatizado (`pg_dump` + `restic`).
  - Ciclo completo de aprendizado (geração automática de rascunho de artigo quando o técnico fecha um chamado), SSO (Google/Microsoft), OCR para PDFs escaneados, conectores Drive/SharePoint e abertura de chamado via e-mail/Teams/WhatsApp.

---

### Roteiro Passo a Passo da Demonstração ao Vivo (5 Atos)

#### Preparação (10 minutos antes de começar)
1. Verifique se a VPS está respondendo verde: acesse `https://h2d-ti.tech/api/ready`.
2. Abra **2 janelas ou perfis de navegador separados** lado a lado (ou fáceis de alternar com `Alt+Tab`):
   - **Janela 1 (Usuário final):** logado como `usuario1@h2d.local` (ou usuário de demo cadastrado na VPS) na tela do **Assistente (Chat)**.
   - **Janela 2 (TI — Admin / Técnico):** logado como **Administrador** (`admin@h2d.local` ou seu usuário admin da VPS) na **Fila de Chamados** ou **Dashboard** (e tenha um acesso de técnico se quiser mostrar a fila filtrada).
3. Confira se os **15 manuais** (`manuais/01` a `manuais/15`) estão ingeridos na base (12 `publico` e 3 `ti`).
4. Se o **Escritório Virtual** (`ESCRITORIO_VIRTUAL_ENABLED=true`) estiver ligado na VPS ou local, deixe o Mini-escritório visível ou uma aba pronta em `/escritorio`.

---

#### Ato 1 — Defleção no Chat com RAG e Citação (Janela 1: Usuário) (~1,5 min)
1. **Ação:** No chat como `usuario1`, faça uma pergunta específica que exige precisão numérica/factual coberta por manual público:
   > *"Por quanto tempo vale a minha senha corporativa e com quantas tentativas erradas a conta bloqueia?"*
2. **O que observar e narrar:**
   - A resposta chega em **streaming (SSE)** com base no **Manual 01** (*Redefinir senha e desbloquear a conta corporativa*): **90 dias** de validade e **5 tentativas** antes do bloqueio por 30 minutos.
   - **Clique na citação/fonte** ao lado para abrir exatamente o trecho usado. Destaque: *"O usuário confia na resposta porque vê de onde ela veio, e se clicar em 👍/Resolver, contabiliza defleção sem gastar tempo da TI."*
3. *(Opcional — pergunta rápida de VPN)*: *"Minha VPN conecta, mas os sistemas internos não abrem. O que faço?"* → cita o Manual 02 (`ipconfig /flushdns`, sessão de 12h).

#### Ato 2 — Segurança: Permissão no SQL e Mascaramento LGPD (Janela 1: Usuário) (~1 min)
1. **Teste de Permissão (`publico` vs. `ti`):**
   - Ainda logado como **usuário comum**, pergunte algo que só existe nos manuais restritos à TI (Manuais 13, 14 ou 15), por exemplo:
     > *"Quais os limites de alerta crítico de uso de disco no servidor Linux e como limpar espaço com docker?"*
   - **O que narrar:** *"Essa informação existe no Manual 14, mas ele tem visibilidade restrita à TI. Como o filtro roda dentro da consulta SQL no pgvector, o assistente não recebe esses trechos e se recusa a inventar uma resposta, oferecendo ajuda da TI."*
2. **Teste de Mascaramento LGPD:**
   - Envie uma mensagem contendo um dado sensível fictício (ex.: *"Tentei entrar com minha senha: MinhaSenha123! e meu CPF 123.456.789-00 não funcionou"* — ou use um CPF válido de teste de algoritmo).
   - **O que narrar:** Mostre que a senha/dado sensível é mascarado antes de persistir ou ir para o LLM (`mask_sensitive`), protegendo dados pessoais e credenciais.

#### Ato 3 — Escalonamento, Classificação IA e Roteador Determinístico (~1 min)
1. **Ação:** Na mesma conversa (ou em uma nova), relate um problema não resolvido / que precisa de ação humana e clique em **"Falar com a TI"** (ou peça um humano):
   > *"Já testei o hotspot do celular e o ipconfig /flushdns, mas o SecureLink continua dando erro de servidor não responde no meu notebook da empresa desde hoje cedo. Preciso de atendimento."*
2. **O que narrar:**
   - O sistema encerra o atendimento no bot e dispara o classificador (saída estruturada Pydantic) + regras em código:
     - Sugere Categoria/Subcategoria, Impacto e Urgência;
     - Calcula **Prioridade e prazo de SLA** em código;
     - **Roteador determinístico** filtra técnicos com habilidade de Rede, disponíveis e com menor carga ponderada;
     - Grava o chamado + evento na tabela `outbox_events` → o **worker** entrega ao **n8n** com assinatura HMAC → **e-mail disparado** ao técnico responsável.

#### Ato 4 — Visão do Técnico, Administração e Dashboard (Janela 2: Admin/Técnico) (~1,5 min)
1. **Fila e Detalhe do Chamado:**
   - Mude para a Janela 2 e abra **Chamados** (atualize ou aguarde a fila). Mostre os filtros (*Em aberto*, *Minha fila*, *Triagem manual*, *Prioridade*).
   - Abra o chamado recém-criado e aponte 3 coisas na tela:
     1. **Resumo gerado pela IA** + **o que já foi tentado** (o técnico entende o problema em 10 segundos sem perguntar tudo de novo);
     2. **Transcrição e fontes consultadas**;
     3. **Linha do tempo auditável:** mostra exatamente *por que* aquele técnico foi escolhido pelo roteador.
2. **Documentos e Ingestão (*Administração → Documentos*):**
   - Mostre a lista dos 15 manuais (públicos e restritos `ti`), o histórico de jobs do worker e explique o **hash SHA-256** (não reprocessa duplicata) + **publicação atômica** (nova versão não tira a anterior do ar se falhar).
3. **Dashboard (*Métricas*):**
   - Mostre os 4 indicadores reais do banco: **Taxa de Defleção**, **Custo por Conversa**, **Volume** e **SLA Cumprido**.

#### Ato 5 — Grand Finale: Escritório Virtual (Opcional / Se Ativo) (~1 min)
1. Abra a tela **Escritório** (`/escritorio`, ou destaque o **Mini-escritório** flutuante).
2. Mostre o **Replay** do atendimento que você acabou de fazer — os bonequinhos percorrendo **Recepção → RAG → Triagem → Banco → Técnicos → Auditoria** — ou rode um dos cenários da aba **Demonstração** caso queira mostrar o fluxo completo sem depender de rede.

---

### Checklist Pré-Apresentação & Plano B (Contingência)

- [ ] **Health check:** `https://h2d-ti.tech/api/ready` respondendo HTTP `200`.
- [ ] **Contas testadas:** login do usuário comum e do admin/técnico funcionando nos dois navegadores antes de compartilhar a tela.
- [ ] **Base populada:** verificar em *Base de Conhecimento* / *Documentos* se os manuais estão ativos.
- [ ] **Cota do OpenRouter:** lembrar que `openrouter/free` usa roteador gratuito (pode ter limite de requisições por minuto ou `LLM_DAILY_REQUEST_LIMIT=45`). Evite ficar testando 20 perguntas seguidas minutos antes da banca!
- [ ] **Se a API do OpenRouter falhar/der timeout ao vivo (Plano B):**
  1. **Não entre em pânico — transforme em ponto positivo:** o sistema foi projetado para **nunca travar sem LLM**. Se o modelo cair, o chat informa indisponibilidade e oferece **abrir o chamado direto**, garantindo continuidade do atendimento.
  2. Mostre os chamados já existentes na fila, a Base de Conhecimento (busca híbrida local com FastEmbed + pgvector funciona 100% sem OpenRouter!), o Dashboard e o modo **Replay / Demonstração** do Escritório Virtual.
- [ ] **Se quiser ensaiar offline sem gastar cota:** rode localmente com `compose.dev.yaml` (sem `OPENROUTER_API_KEY`, o sistema usa o comportamento seguro de indisponibilidade, ou `FakeLLM` nos testes; e `--profile n8n` sobe o Mailpit em `http://localhost:8025` para mostrar os e-mails na tela).
