# H2D - TI: Todo List

Detalhes e critérios de saída: [PLANO-IMPLEMENTACAO.md](PLANO-IMPLEMENTACAO.md).

**Como usar:** marque `[x]` ao concluir e atualize o status da fase no quadro abaixo. Uma fase só termina quando os critérios de saída estão marcados e o `/qa` passou. Depois que o repositório estiver no GitHub, cada item vira uma issue de 0,5 a 2 dias.

**Entrega: 18/11/2026.** Itens riscados foram cortados pelo prazo (seção 6 do plano).

**Responsáveis (sugestão):** `TL` tech lead, `A` Colega A (front), `B` Colega B (dados e automação). Darles e Hanover ainda vão definir quem assume A e B. **Status:** `pending`, `in_progress`, `completed`, `blocked`.

```
Progresso
⬤ [in_progress] F0 Decisões (04/11 a 05/11)
⬤ [in_progress] F1 Fundação (05/11 a 07/11)
⬤ [pending] F2 Ingestão (06/11 a 09/11)
⬤ [pending] F3 Chat RAG (08/11 a 11/11)
⬤ [pending] F4 Triagem e chamados (10/11 a 14/11, marco: fluxo mínimo)
⬤ [pending] F5 Automações (14/11 a 15/11)
⬤ [pending] F6 Dashboard (14/11 a 16/11)
⬤ [pending] F7 Endurecimento e demo (15/11 a 17/11)
```

## F0. Decisões

- [x] `TL` Descobrir a data de entrega do curso: 18/11/2026
- [ ] `TL` Dar acesso ao repositório a Darles e Hanover
- [ ] `TL` Confirmar Python no backend com os colegas e escrever o ADR-001
- [ ] `TL` Confirmar o plano do GitHub (repositório criado como privado)
- [ ] `TL` Definir o canal de notificação e o volume esperado do piloto
- [ ] `TL` Resolver as divergências D1 a D9 do plano
- [ ] `TL` Combinar a divisão de tarefas conforme o que cada um domina
- [ ] `TL` Contratar a VPS e registrar o domínio
- [ ] `TL` Criar a conta no OpenRouter com limite de gasto

## F1. Fundação

**Repositório e ambiente**
- [x] `TL` Rodar `git init` e criar o repositório no GitHub
- [ ] `TL` Criar a estrutura do monorepo
- [ ] `TL` Configurar proteção da `main`, CODEOWNERS e templates de issue e PR
- [ ] `B` Criar Makefile, `.env.example` e pre-commit com gitleaks
- [ ] `TL` Criar o Compose local (db, api, worker, web), com init dos bancos `h2d` e `n8n`
- [ ] `TL` Criar o GitHub Projects e a milestone da fase

**Backend**
- [ ] `TL` Estruturar FastAPI, SQLAlchemy, Alembic, `/health` e `/ready`
- [ ] `TL` Revisar o modelo de dados completo, incluindo as tabelas da divergência D5
- [ ] `TL` Migrar o grupo Cadastro e `audit_log`, com IDs UUID v7 gerados na aplicação
- [ ] `TL` Implementar auth com JWT em cookie, argon2 e papéis
- [ ] `B` Criar o seed de usuários, técnicos, habilidades, categorias e SLAs

**Frontend**
- [ ] `A` Criar o projeto Vite com TanStack Router e Query, Tailwind e shadcn/ui
- [ ] `A` Criar `tokens.css` e validar o contraste dos dois temas
- [ ] `A` Montar o layout: barra lateral, cabeçalho em caminho e barra de status
- [ ] `A` Criar a tela de login e a proteção de rotas por papel
- [ ] `A` Gerar o cliente a partir do OpenAPI

**CI e VPS**
- [ ] `TL` Configurar CI: lint, tipos, testes com pgvector, contrato, build e varredura de segurança
- [ ] `TL` Ativar Dependabot e, se o repositório for público, secret scanning com push protection
- [ ] `TL` Endurecer a VPS: SSH por chave, ufw, fail2ban e atualizações automáticas
- [ ] `TL` Configurar Caddy com TLS e cabeçalhos básicos
- [ ] `TL` Configurar deploy via GHCR com aprovação manual e checagem de `/ready`

**Critérios de saída**
- [ ] Login do seed funciona em HTTPS na VPS
- [ ] Mudança de contrato não commitada quebra o CI
- [ ] Merge na `main` chega à VPS com `/ready` verde
- [ ] Banco inacessível de fora da VPS

## F2. Ingestão

- [ ] `TL` Fazer o spike de embeddings e escrever o ADR-002
- [ ] `TL` Migrar o grupo Conhecimento (índice HNSW, `tsvector`, `pg_trgm`)
- [ ] `TL` Configurar o worker com Procrastinate
- [ ] `TL` Implementar registro, SHA-256 e guarda do arquivo original
- [ ] `TL` Implementar parsing com Docling e limpeza
- [ ] `TL` Implementar chunking por título, sem partir tabelas nem passos numerados
- [ ] `TL` Implementar embeddings em lote, publicação atômica e arquivamento
- [ ] `TL` Implementar busca híbrida com RRF, filtro de visibilidade e varredura iterativa
- [ ] `TL` Criar endpoints de upload, jobs, reindexação e busca, com limite de tipo e tamanho
- [ ] `A` Criar a tela de ingestão, com jobs e versões
- [ ] `A` Criar a tela de base de conhecimento
- [ ] `B` Finalizar 10 a 15 manuais fictícios
- [ ] `B` Criar o conjunto de avaliação v0, com 30 perguntas
- [ ] `TL` Medir memória com `docker stats` e definir limites por container

**Critérios de saída**
- [ ] Arquivo duplicado não reprocessa; versão nova arquiva a anterior após publicar
- [ ] Falha no job não deixa versão parcial ativa, e o motivo aparece na tela
- [ ] Teste automatizado: usuário comum nunca recebe trecho restrito à TI
- [ ] Linha de base de acerto top-k registrada

## F3. Chat RAG

- [ ] `TL` Criar o cliente LLM, o `FakeLLM` e a tabela `llm_calls`
- [ ] `TL` Implementar mascaramento de senha, CPF, cartão e token
- [ ] `TL` Implementar limites de turnos, tokens e requisições
- [ ] `TL` Migrar conversas e mensagens; documentar as tabelas do checkpointer
- [ ] `TL` Implementar `prompt_versions` e gravar a versão em cada resposta
- [ ] `TL` Implementar o grafo LangGraph: reescrita, busca e geração com trechos delimitados
- [ ] `TL` Implementar checagem de fidelidade, limiar de confiança e gatilhos de escalonamento
- [ ] `TL` Criar endpoints de conversas, histórico, mensagens em SSE, feedback e `escalate`
- [ ] `A` Criar a tela de chat com SSE via `fetch`, começando com stream simulado
- [ ] `A` Criar o painel de fontes, `CitationCard` e 👍/👎
- [ ] `A` Incluir o botão "falar com a TI" e o aviso sobre uso de IA
- [ ] `B` Rodar a avaliação no CI (10 casos por PR, conjunto completo à noite)
- [ ] `B` Escrever casos de prompt injection nos manuais de teste
- [ ] Todos: definir as metas de acerto com base nas medições

**Critérios de saída**
- [ ] Resposta coberta traz citação que abre o trecho certo
- [ ] Pergunta fora da base recebe "não encontrei"
- [ ] Instrução maliciosa em manual não altera o comportamento
- [ ] Senha colada não aparece em log, banco nem chamada ao LLM
- [ ] Metas de acerto definidas e medidas

## F4. Triagem e chamados

- [ ] `TL` Migrar `tickets`, `ticket_events`, `outbox_events` e `app_settings`
- [ ] `TL` Adicionar a ferramenta `get_my_tickets` ao agente, somente leitura e limitada ao próprio usuário
- [ ] `TL` Implementar o classificador com saída Pydantic e categorias do banco
- [ ] `TL` Implementar a matriz de prioridade e o cálculo de prazo de SLA em código
- [ ] `TL` Implementar o roteador, com testes unitários e motivo gravado
- [ ] `TL` Implementar a fila de triagem manual
- [ ] `TL` Implementar perguntas de esclarecimento, tema crítico e criação do chamado
- [ ] `TL` Implementar a abertura de chamado sem classificação quando o LLM cair
- [ ] `TL` Criar endpoints de chamados, com autorização por papel
- [ ] `TL` Implementar a entrega do outbox com `event_id` e novas tentativas
- [ ] `TL` Implementar assinatura HMAC nos dois sentidos
- [ ] `B` Subir o n8n no Compose, com banco próprio e editor privado
- [ ] `B` Criar o workflow 1 (aviso de chamado, com P1 avisando também o líder) e exportar para o repositório
- [ ] `B` Criar o conjunto rotulado inicial, com 30 conversas
- [ ] ~~`B` Criar os CRUDs de usuários, técnicos, habilidades, categorias, SLAs e regras de roteamento, gravando em `audit_log`~~ (cadastros ficam no seed)
- [ ] `A` Criar a fila com `DataTable`, filtros e `j`/`k`
- [ ] `A` Criar o detalhe do chamado: resumo, transcrição, fontes, ações e solução
- [ ] `A` Criar "meus chamados" com linha do tempo

**Critérios de saída (marco: fluxo mínimo)**
- [ ] Demo completa na VPS, com usuário e técnico em navegadores separados
- [ ] n8n fora do ar: o aviso chega ao religar, sem duplicar
- [ ] LLM fora do ar: o chat oferece abrir chamado direto
- [ ] Usuário só vê os próprios chamados
- [ ] Acerto de categoria medido

## F5. Automações

- [ ] `B` Criar o workflow 5 (erro global)
- [ ] `TL` Criar o endpoint assinado de chamados em risco
- [ ] `B` Criar o workflow 2 (vigia de SLA)
- [ ] ~~`TL` Criar o endpoint de avaliação CSAT~~
- [ ] ~~`A` Criar a tela de avaliação do chamado~~
- [ ] ~~`B` Criar o workflow 4 (pesquisa de satisfação)~~
- [ ] ~~`B` Criar o workflow 3 (relatório semanal)~~
- [ ] `B` Configurar a poda do histórico de execuções
- [ ] `TL` Guardar a `N8N_ENCRYPTION_KEY` fora da VPS

**Critérios de saída**
- [ ] Alertas de 75% e 100% disparam uma única vez cada
- [ ] Chamada sem assinatura válida recebe 401
- [ ] Workflow com falha forçada avisa o canal de TI

## F6. Dashboard

- [ ] `TL` Criar os endpoints de métricas: defleção, custo, volume e SLA
- [ ] `A` Criar `KpiTile`
- [ ] `A` Exibir taxa de defleção e custo por conversa **(obrigatórios)**
- [ ] `A` Exibir volume e SLA cumprido
- [ ] ~~`A` Criar `Sparkline`~~
- [ ] ~~`A` Exibir backlog, MTTR, 1ª resposta humana, acerto da classificação e CSAT~~
- [ ] ~~`A` Criar a tela "Minha carga" e exibir lacunas da base e custo por chamado~~
- [ ] `B` Conferir cada KPI com uma consulta SQL escrita à mão

**Critérios de saída**
- [ ] Todos os KPIs exibidos conferem com o SQL manual
- [ ] Técnico lê o dashboard, mas não altera nada

## F7. Endurecimento e piloto

**Operação**
- [ ] `TL` Configurar `pg_dump` diário e restic para armazenamento externo
- [ ] `TL` Restaurar o backup em ambiente limpo e cronometrar
- [ ] ~~`TL` Configurar Uptime Kuma e Sentry/GlitchTip~~
- [ ] `TL` Configurar CSP, HSTS e limite de requisições por IP
- [ ] `B` Escrever o runbook: reiniciar, restaurar e rotacionar chaves

**Qualidade**
- [ ] `B` Criar o teste e2e com Playwright para o fluxo chat → chamado
- [ ] `B` Fechar os conjuntos com 30 perguntas de RAG e 30 conversas rotuladas
- [ ] `TL` Calibrar os limiares de confiança com as medições
- [ ] `A` Fazer a auditoria de acessibilidade (foco, contraste, movimento reduzido)
- [ ] ~~`A` Criar a paleta `Ctrl+K` e os atalhos globais~~

**Admin e conformidade**
- [ ] ~~`TL` Criar a tela de configuração de IA~~
- [ ] ~~`A` Criar a tela de auditoria~~
- [ ] `TL` Definir retenção, exclusão a pedido e revisar a política do provedor de LLM
- [ ] ~~`TL` Migrar `kb_drafts` e gerar rascunho de artigo a partir da solução, com aprovação do admin~~

**Demo**
- [ ] `B` Preparar os dados de demonstração e o roteiro
- [ ] Todos: ensaiar a demo na VPS

**Critérios de saída**
- [ ] Backup restaurado, com tempo registrado
- [ ] Critérios de sucesso do MVP todos marcados
- [ ] Demo ensaiada sem intervenção manual

## Backlog pós-MVP

- [ ] Pós-entrega: retomar os itens riscados acima
- [ ] Fase 1.5: reranking, se a avaliação mostrar ganho
- [ ] Fase 1.5: workflow 6 (validade de documentos)
- [ ] Fase 2: SSO, anexos e PWA
- [ ] Fase 2: chat ao vivo com o técnico e entrada multimodal
- [ ] Fase 2: conectores Drive/SharePoint e OCR
- [ ] Fase 2: e-mail para chamado, Teams/WhatsApp
- [ ] Fase 2: escala de plantão e reatribuição automática por SLA
- [ ] Fase 2: inventário de ativos e catálogo de serviços
