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

**Estado em 05/11/2026: 3 de 9 itens concluídos. O que falta depende de você ou do time e está nas issues indicadas.**

- [x] `TL` Descobrir a data de entrega do curso: 18/11/2026
- [x] `TL` Resolver as divergências D1 a D11 do plano ([ADR-002](adr/0002-divergencias-do-plano.md))
- [x] `TL` Registrar as premissas do canal de notificação e do volume do piloto (ADR-002); a confirmação com o time de TI está em #12
- [ ] `TL` Dar acesso ao repositório a Darles e Hanover (#6)
- [ ] `TL` Confirmar Python no backend com os colegas; o [ADR-001](adr/0001-python-no-backend.md) segue como proposta (#7)
- [ ] `TL` Decidir o plano do GitHub: no plano atual a proteção da `main` e a aprovação do ambiente não funcionam (#8)
- [x] `TL` Contratar a VPS (KVM 2, Hostinger). Domínio temporário em uso: `h2d.187-127-0-175.sslip.io`
- [ ] `TL` Registrar o domínio definitivo (#9)
- [ ] `TL` Criar a conta no OpenRouter com limite de gasto (#10)
- [ ] `TL` Combinar a divisão de tarefas conforme o que cada um domina (#11)

## F1. Fundação

**Estado em 05/11/2026: o sistema está no ar na VPS (stack do Portainer, HTTPS no domínio temporário). Faltam a proteção da `main`, o Projects e fechar os critérios de saída na VPS (#13).**

**Repositório e ambiente**
- [x] `TL` Rodar `git init` e criar o repositório no GitHub
- [x] `TL` Criar a estrutura do monorepo
- [ ] `TL` Configurar proteção da `main`: bloqueada pelo plano do GitHub (#8). CODEOWNERS e templates já existem
- [x] `B` Criar Makefile, `.env.example` e pre-commit com gitleaks
- [x] `TL` Criar o Compose local (db, api, web), com init dos bancos `h2d` e `n8n`; o worker entra na F2
- [x] `TL` Criar milestones F0 a F7, labels de área e as issues pendentes e da F2
- [ ] `TL` Criar o GitHub Projects: o token da CLI não tem o escopo `project` (#14)

**Backend**
- [x] `TL` Estruturar FastAPI, SQLAlchemy, Alembic, `/api/health` e `/api/ready`
- [x] `TL` Revisar o modelo de dados completo e as tabelas da D5 ([MODELO-DADOS.md](MODELO-DADOS.md))
- [x] `TL` Migrar o grupo Cadastro e `audit_log`, com IDs UUID v7 gerados na aplicação
- [x] `TL` Implementar auth com JWT em cookie, argon2 e papéis
- [x] `B` Criar o seed de usuários, técnicos, habilidades, categorias e SLAs (prazos de SLA provisórios)
- [x] `TL` Criar `h2d.create_admin` para o primeiro administrador em produção, e exigir `ALLOW_DEMO_SEED` para rodar o seed lá
- [x] `TL` Criar a API de usuários (`/api/users`: listar, criar, editar, desativar e redefinir senha; só admin; grava em `audit_log`). Senha com 6+ caracteres, letras e números
- [x] `TL` Convite por e-mail: link de uso único (48 h) para a pessoa definir a própria senha, e-mail no tema do app via n8n, reenvio de link (migração 0005)

**Frontend**
- [x] `A` Criar o projeto Vite com TanStack Router e Query e Tailwind
- [x] `A` Decidir sobre o shadcn: não usar o CLI, e remover o `components.json` (D11)
- [x] `A` Criar `tokens.css` e validar o contraste dos dois temas (teste automatizado)
- [x] `A` Montar o layout de ERP: menu por módulos, breadcrumbs, busca `Ctrl+K` e notificações
- [x] `A` Criar o kit: badges, snippets, tabelas, abas, modais, painéis, gráficos e avisos
- [x] `A` Criar as telas com dados de demonstração (divergência D10)
- [x] `TL` Cadastros: **Usuários** ganhou backend (API só para admin, com auditoria, e tela ligada). Técnicos, categorias e SLAs seguem em demonstração, e Auditoria e Configurações ficam com o selo (#15)
- [x] `A` Criar a tela de login e a proteção de rotas por papel
- [x] `A` Gerar o cliente a partir do OpenAPI

**CI e VPS**
- [x] `TL` Escrever o CI: lint, tipos, testes com pgvector, contrato, build e varredura de segurança
- [x] `TL` Confirmar o CI verde no GitHub (5 de 5 jobs na `main`, commit `b94bce5`)
- [x] `TL` Incluir o Trivy no CI, testado localmente nos dois sentidos; a única exceção está em `.trivyignore`, com prazo até 05/12/2026
- [x] `TL` Configurar Dependabot, ignorando saltos de versão que quebram (TypeScript 7, Node, Python)
- [ ] `TL` Ativar secret scanning com push protection: só em repositório público (#8)
- [x] `TL` Escrever `harden-vps.sh` (SSH só por chave, ufw, fail2ban, atualizações automáticas): passou em `shellcheck`, **nunca foi executado**
- [x] `TL` Escrever o Caddyfile com TLS e cabeçalhos básicos (configuração validada, sem uso real)
- [x] `TL` Criar o Compose de produção: validado com `docker compose config`, **nunca subiu**
- [x] `TL` Escrever o deploy via GHCR e `deploy.sh` com rollback e checagem de `/api/ready`: validado com `actionlint`, **nunca rodou**. Roda só por disparo manual, porque o GitHub não aplica aprovação de ambiente neste plano
- [x] `TL` Fazer o primeiro deploy na VPS por um stack do Portainer que compila do Git (`docker-compose.yml`); o desenho por SSH (`compose.prod.yaml`, `deploy.yml`) ficou sem uso. Ver o [runbook](RUNBOOK-VPS.md) (#13)
- [ ] `TL` Fechar os critérios de saída da F1 na VPS: login do administrador, varredura de portas de fora e atualização por merge (#13)

**Critérios de saída**
- [ ] Login do seed funciona em HTTPS na VPS (local em HTTP: testado no navegador) (#13)
- [ ] Mudança de contrato não commitada quebra o CI (o job passa com o contrato em dia; a detecção foi provada só localmente)
- [ ] Merge na `main` chega à VPS com `/api/ready` verde (#13)
- [ ] Banco inacessível de fora da VPS (o Compose de produção não publica a porta; falta testar com varredura de fora) (#13)

## F2. Ingestão

- [x] `TL` Fazer o spike de embeddings e escrever o [ADR-003](adr/0003-embeddings.md): MiniLM multilíngue local, 384 dimensões
- [x] `TL` Migrar o grupo Conhecimento (migração 0002: `kb_documents`, versões, `kb_chunks` com `vector(384)`, HNSW e `tsvector`, `ingestion_jobs`)
- [x] `TL` Configurar o worker: **sem Procrastinate**; a fila é a própria tabela `ingestion_jobs`, com `SKIP LOCKED` e reenfileiramento de job travado (`h2d.worker`, serviço `worker` no compose)
- [x] `TL` Implementar registro, SHA-256 e guarda do arquivo original (volume `h2d_uploads`)
- [x] `TL` Implementar parsing e limpeza: Markdown, texto, **PDF e DOCX** por extração de texto (`h2d.kb.parsing`, bibliotecas leves; o **Docling foi descartado** pelo peso na VPS). Reconhece títulos, listas e tabelas, tira cabeçalho, rodapé e número de página repetidos, e recusa com motivo PDF digitalizado (sem OCR), com senha ou quebrado
- [x] `TL` Implementar chunking por título, sem partir tabelas nem passos numerados (`h2d.kb.text`, testado nos 15 manuais; falta medir o limite de tokens do MiniLM e ligar ao pipeline)
- [x] `TL` Implementar embeddings em lote, publicação atômica e arquivamento
- [x] `TL` Implementar busca híbrida com RRF, filtro de visibilidade e varredura iterativa
- [x] `TL` Criar endpoints de upload, jobs, reindexação e busca, com limite de tipo e tamanho (`/api/kb/*`)
- [x] `A` Criar a tela de ingestão, com jobs e versões (Administração → Documentos: envio, fila ao vivo, histórico com o motivo da falha, edição e reindexação)
- [x] `A` Criar a tela de base de conhecimento (biblioteca por categoria, busca e documento aberto em seções; conteúdo restrito à TI não aparece para usuário comum)
- [x] `B` Escrever 15 manuais fictícios (12 públicos e 3 restritos à TI), só locais em `manuais/` (fora do Git, enviados pela tela de ingestão). `B` ainda revisa o conteúdo
- [ ] `B` Criar o conjunto de avaliação v0, com 30 perguntas
- [x] `TL` Medir memória com `docker stats` (desenvolvimento): API ~700 MB e worker ~970 MB com o modelo carregado. Falta medir na VPS e decidir sobre a KVM 4

**Critérios de saída**
- [x] Arquivo duplicado não reprocessa; versão nova arquiva a anterior após publicar (testado)
- [x] Falha no job não deixa versão parcial ativa (testado), e o motivo aparece na tela
- [x] Teste automatizado: usuário comum nunca recebe trecho restrito à TI (busca, trecho citado e biblioteca; conferido também com o modelo real: 0 trechos de TI para o usuário comum)
- [x] Linha de base de acerto top-k registrada (conjunto de 22 perguntas escritas por `TL`, modelo real, 15 manuais): top-1 13/22, top-3 17/22, top-5 20/22. Abaixo da meta: ver melhorias em [ADR-003](adr/0003-embeddings.md)

## F3. Chat RAG

- [x] `TL` Criar o cliente LLM (OpenRouter, com modelos de reserva e novas tentativas), o `FakeLLM` e a tabela `llm_calls` (custo em `numeric`). Testado com o modelo real
- [x] `TL` Implementar mascaramento de senha, CPF, cartão e token (`h2d.chat.masking`, antes de gravar ou enviar ao modelo)
- [x] `TL` Implementar limites de turnos, tamanho da mensagem e requisições ao modelo por dia (`LLM_DAILY_REQUEST_LIMIT`, padrão 45 por causa do plano gratuito)
- [x] `TL` Migrar conversas e mensagens (migração 0003). **Sem LangGraph:** o fluxo é um pipeline simples em funções, então não há tabelas de checkpointer
- [x] `TL` Implementar `prompt_versions` e gravar a versão em cada resposta
- [x] `TL` Implementar o fluxo do chat (sem LangGraph): reescrita, busca, geração com trechos delimitados e citação
- [x] `TL` Implementar checagem de fidelidade, resposta só com citação e gatilhos de escalonamento (tema crítico, pedido de humano, duas respostas sem ajudar)
- [x] `TL` Criar endpoints de conversas, histórico, mensagens em SSE (resposta já pronta, enviada em pedaços), feedback, `resolve` e `escalate` (`/api/chat/*`)
- [x] `A` Criar a tela de chat com SSE via `fetch` (resposta pronta enviada em pedaços; Markdown, "Nova conversa", conversa encerrada bloqueia o campo)
- [x] `A` Criar o painel de fontes (clicar abre o trecho citado) e 👍/👎
- [x] `A` Incluir o botão "falar com a TI" e o aviso sobre uso de IA
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

- [x] `TL` Migrar `tickets`, `ticket_events`, `outbox_events` e `app_settings` (migração 0004)
- [ ] `TL` Adicionar a ferramenta `get_my_tickets` ao agente, somente leitura e limitada ao próprio usuário
- [x] `TL` Implementar o classificador com saída Pydantic e categorias do banco (categoria fora da lista vira triagem manual)
- [x] `TL` Implementar a matriz de prioridade e o cálculo de prazo de SLA em código (`h2d.tickets.rules`)
- [x] `TL` Implementar o roteador, com testes unitários e motivo gravado em `ticket_events`
- [x] `TL` Implementar a fila de triagem manual (backend: filtro `triage` e reatribuição pelo admin; falta a tela)
- [ ] `TL` Implementar perguntas de esclarecimento, tema crítico e criação do chamado
- [x] `TL` Implementar a abertura de chamado sem classificação quando o LLM cair
- [x] `TL` Criar endpoints de chamados, com autorização por papel (`/api/tickets`)
- [x] `TL` Implementar a entrega do outbox com `event_id` e novas tentativas (espera crescente, desiste em 10; roda no worker)
- [x] `TL` Implementar assinatura HMAC nos dois sentidos (API para n8n com cabeçalhos assinados; rotas `/api/hooks/n8n/*` conferem a assinatura)
- [x] `B` Subir o n8n no Compose, com banco próprio e editor privado (imagem própria com os workflows; perfil `n8n` no desenvolvimento, com Mailpit)
- [x] `B` Criar o workflow 1 (aviso de chamado, com P1 avisando também o líder) e exportar para o repositório (`n8n/workflows/01-aviso-de-chamado.json`; testado de ponta a ponta com o Mailpit)
- [x] `B` Criar o conjunto rotulado inicial, com 30 conversas (`eval/classificacao_v0.jsonl`; `python -m h2d.eval_classification`)
- [ ] ~~`B` Criar os CRUDs de usuários, técnicos, habilidades, categorias, SLAs e regras de roteamento, gravando em `audit_log`~~ (cadastros ficam no seed)
- [x] `A` Criar a fila com `DataTable` e filtros (todos, em aberto, minha fila, triagem manual com contador, prioridade). Falta o atalho `j`/`k`
- [x] `A` Criar o detalhe do chamado: resumo, o que já foi tentado, transcrição, linha do tempo com o motivo da atribuição, ações do técnico, reatribuição pelo admin e solução
- [x] `A` Criar "meus chamados" com linha do tempo e comentários

**Critérios de saída (marco: fluxo mínimo)**
- [ ] Demo completa na VPS, com usuário e técnico em navegadores separados
- [x] n8n fora do ar: o aviso chega ao religar, sem duplicar (testado com o n8n real: fila, nova tentativa e reentrega sem e-mail repetido)
- [ ] LLM fora do ar: o chat oferece abrir chamado direto
- [ ] Usuário só vê os próprios chamados
- [x] Acerto de categoria medido: em 12 das 30 conversas, categoria 11/12, subcategoria 10/12, prioridade exata 8/12 e até 1 nível 12/12 (depois de calibrar o prompt; antes a prioridade exata era 3/12). Faltam as outras 18 conversas e um conjunto escrito por outra pessoa

## F5. Automações

- [x] `B` Criar o workflow 5 (erro global): avisa o líder com o workflow, o nó e o erro (testado com falha forçada)
- [x] `TL` Criar o endpoint assinado de chamados em risco (`POST /api/hooks/n8n/sla-check`: cria os alertas de 75% e 100% e os enfileira no outbox)
- [x] `B` Criar o workflow 2 (vigia de SLA): a cada 5 minutos, assinado com HMAC
- [ ] ~~`TL` Criar o endpoint de avaliação CSAT~~
- [ ] ~~`A` Criar a tela de avaliação do chamado~~
- [ ] ~~`B` Criar o workflow 4 (pesquisa de satisfação)~~
- [ ] ~~`B` Criar o workflow 3 (relatório semanal)~~
- [x] `B` Configurar a poda do histórico de execuções (só erros, 7 dias)
- [ ] `TL` Guardar a `N8N_ENCRYPTION_KEY` fora da VPS (instrução no runbook; falta você guardar a cópia)

**Critérios de saída**
- [x] Alertas de 75% e 100% disparam uma única vez cada (testado: no código, e no n8n real, com 2 ciclos do agendamento e 1 e-mail por nível)
- [x] Chamada sem assinatura válida recebe 401 (API e webhook do n8n)
- [x] Workflow com falha forçada avisa o canal de TI (API derrubada: o líder recebeu o aviso)

## F6. Dashboard

- [x] `TL` Criar os endpoints de métricas: defleção, custo, volume e SLA (`GET /api/metrics/overview?days=`; definições no topo de `apps/api/src/h2d/metrics.py`)
- [x] `A` Criar `KpiTile`
- [x] `A` Exibir taxa de defleção e custo por conversa **(obrigatórios)**
- [x] `A` Exibir volume e SLA cumprido
- [ ] ~~`A` Criar `Sparkline`~~
- [ ] ~~`A` Exibir backlog, MTTR, 1ª resposta humana, acerto da classificação e CSAT~~
- [ ] ~~`A` Criar a tela "Minha carga" e exibir lacunas da base e custo por chamado~~
- [x] `B` Conferir cada KPI com uma consulta SQL escrita à mão (`apps/api/tests/test_metrics.py` e conferência manual no banco de desenvolvimento)

**Critérios de saída**
- [x] Todos os KPIs exibidos conferem com o SQL manual
- [x] Técnico lê o dashboard, mas não altera nada (teste de papel: técnico 200, usuário 403, escrita 405)

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
