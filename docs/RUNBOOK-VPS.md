# Runbook: VPS e deploy

**Estado em 05/11/2026:** o H2D roda na VPS Hostinger (KVM 2, Ubuntu 24.04), num stack do Portainer que compila direto do Git. Está em `https://h2d.187-127-0-175.sslip.io` (domínio temporário; troque pelo definitivo quando existir).

## Como é o desenho

- **Proxy:** um único Caddy recebe as portas 80 e 443, gera o HTTPS e encaminha pela rede Docker externa `proxy`. Os apps não publicam portas. A configuração dele fica em `/opt/proxy/caddy/Caddyfile`, na VPS, fora deste repositório.
- **Stack `h2d-ti`** ([`docker-compose.yml`](../docker-compose.yml), na raiz): `h2d-db` (pgvector), `h2d-api`, `h2d-web` (SPA + Caddy interno em HTTP na 8080) e `h2d-n8n`. Só `h2d-web` e `h2d-n8n` entram na rede `proxy`.
- **Imagens:** o Portainer faz o build (`pull_policy: build`). Nada de GHCR nem SSH.
- **Segredos:** só em *Environment variables* do stack, no Portainer. Nunca no Git. Os nomes estão no [`.env.example`](../.env.example).
- **Outros projetos na mesma VPS** (HispanoPro, OrcaGenius, SteelDeck, Portainer): não os altere por causa do H2D.

## Primeiro deploy (ou refazer do zero)

1. Portainer → Stacks → Add stack → **Repository**.
2. URL `https://github.com/danubiolagoa/h2d-ti`, referência `refs/heads/main`, caminho `docker-compose.yml`. O repositório é privado: ative *Authentication* com um token do GitHub **só de leitura** (fine-grained, Contents: Read-only).
3. Variáveis: `POSTGRES_PASSWORD`, `H2D_DB_PASSWORD`, `N8N_DB_PASSWORD`, `JWT_SECRET`, `N8N_ENCRYPTION_KEY`, `N8N_DOMAIN`. Gere cada segredo com `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
4. **Deploy the stack.** O primeiro build leva alguns minutos.
5. Crie o administrador, no console do `h2d-api` (senha de 6+ caracteres, com letras e números):

```bash
ADMIN_EMAIL=voce@empresa.com ADMIN_NAME="Seu Nome" ADMIN_PASSWORD='sua-senha' python -m h2d.create_admin
```

6. Os demais usuários são criados no painel: **Administração → Cadastros → Novo: usuário**.

## Atualizar

Faça merge na `main` e, no Portainer, Stacks → `h2d-ti` → **Pull and redeploy**. Confira `https://<domínio>/api/ready`. As migrações rodam sozinhas quando a API sobe.

**Armadilhas já vistas:**
- **Bind mount com caminho relativo não funciona** no Portainer: o Docker cria uma pasta vazia no lugar do arquivo. Por isso o script de init do banco vai dentro da imagem (`infra/db/Dockerfile`). Não use `./arquivo:/destino` no compose.
- O script de init do banco roda **só na primeira criação do volume**. Mudar a senha do banco depois não altera a que o Postgres já guardou.
- Se refizer o stack, **não marque** a remoção de volumes, a menos que queira apagar o banco.
- **O Hugging Face limita o download do modelo de embeddings (erro 429)**, e isso já derrubou um build. O Dockerfile tenta 5 vezes e não quebra mais o deploy: se não conseguir, a API baixa o modelo na primeira execução (com novas tentativas) e o guarda no volume `h2d_models`. Se o 429 persistir, crie um token gratuito em huggingface.co/settings/tokens e cadastre `HF_TOKEN` nas variáveis do stack.

## Rollback

O rollback não desfaz migrações. Toda migração precisa funcionar também com o código da versão anterior: primeiro adicione, depois use, só então remova. Para voltar o código, reverta o commit na `main` e faça **Pull and redeploy**.

## n8n e os avisos de chamado

O n8n sobe no stack, com banco próprio (`n8n`) e **sem endereço público** (decisão D4): o editor só é alcançado se o Caddy da VPS ganhar um bloco para `N8N_DOMAIN`, de preferência com senha ou restrito a um IP. A API entrega os eventos ao n8n pela rede interna (`http://h2d-n8n:5678/webhook/h2d-events`), assinados com HMAC.

**Variáveis (Portainer):** `N8N_HMAC_SECRET` (obrigatória para os avisos; gere como os outros segredos), `TI_LEADER_EMAIL` (recebe a triagem manual e os P1), `MAIL_FROM` e `H2D_BASE_URL` (link no e-mail). Sem o `N8N_HMAC_SECRET` os eventos ficam na fila e nada é enviado.

**Configuração única, depois do primeiro deploy:**

1. Abra o editor do n8n e crie o dono (quem abrir primeiro vira dono). Guarde `N8N_ENCRYPTION_KEY` fora da VPS.
2. No console do container `h2d-n8n`, importe os workflows (a imagem já leva os arquivos) e publique os três, **o de erro primeiro**:

```bash
n8n import:workflow --separate --input=/home/node/h2d-workflows
```

```bash
n8n publish:workflow --id=h2d-erro-global
```

```bash
n8n publish:workflow --id=h2d-aviso-chamado
```

```bash
n8n publish:workflow --id=h2d-vigia-sla
```

3. Reinicie o container `h2d-n8n`.
4. No editor, crie a credencial **SMTP** com o nome exato `SMTP H2D` (servidor, porta, usuário e senha do e-mail que enviará os avisos) e abra os workflows "H2D 01 - Aviso de chamado" e "H2D 05 - Erro global" para conferir que o nó "Enviar e-mail" a usa.

**Como conferir:** abra um chamado pelo assistente. O evento aparece em `outbox_events` como `delivered` e o aviso chega ao técnico responsável (ou ao líder, se for triagem manual).

**Workflows:**
- **01 Aviso de chamado:** recebe os eventos da API (chamado criado, atribuído, resolvido e alerta de SLA) e envia o e-mail.
- **02 Vigia de SLA:** a cada 5 minutos chama `/api/hooks/n8n/sla-check`. A API cria o alerta de **75%** e o de **100%** do prazo, **uma única vez cada**, e o aviso sai pelo workflow 01 (o de 100% copia o líder). O alerta vai pela fila de eventos, então e-mail que falha não perde nem repete o aviso.
- **05 Erro global:** qualquer workflow que falhar avisa o `TI_LEADER_EMAIL` com o nome, o nó e o erro.

**Poda:** o n8n guarda só as execuções com erro, por 7 dias (`EXECUTIONS_DATA_*` no compose).

**Comportamento:**
- Assinatura inválida: o n8n responde 401 e o evento continua pendente (nunca é dado como entregue).
- n8n fora do ar ou e-mail falhando: o evento tenta de novo com espera crescente (30 s, 1 min, 2 min... até 1 h) e desiste depois de 10 tentativas, ficando `failed` para revisão.
- O mesmo evento reenviado não duplica o e-mail (o n8n guarda os últimos 500 `event_id`).

**Testar no seu PC:** `docker compose --profile n8n up -d` sobe o n8n (porta 5679) e o Mailpit (<http://localhost:8025>), que recebe os e-mails em vez de enviá-los. Importe a credencial e o workflow como acima.

## Catálogo e técnicos em produção

Os chamados só são atribuídos automaticamente se existirem categorias, habilidades, prazos de SLA e técnicos. O seed de demonstração cria tudo isso, mas também cria usuários de mentira; em produção use o script abaixo, no console do container `h2d-api`. Ele só cria o que falta:

```bash
TECHNICIAN_EMAILS=tecnico1@empresa.com,tecnico2@empresa.com python -m h2d.bootstrap_catalog
```

Cada e-mail precisa ser de um usuário que já existe, com papel técnico ou administrador (crie pelo painel em Cadastros). Sem técnicos, todo chamado vai para a triagem manual.

## Checklist dos critérios de saída da F1

- [x] Site e `/api/ready` respondem 200 em HTTPS
- [ ] Login do administrador funciona em `https://<domínio>`
- [ ] Banco inacessível de fora: varredura de portas (`nmap -Pn 187.127.0.175`) sem a 5432
- [ ] Merge na `main` chega à VPS com `/api/ready` verde (hoje com *Pull and redeploy* manual)

## Pendências de segurança da VPS

- Portainer exposto em HTTP na porta 9001 e na versão 2.39 (a 2.45 corrige falhas críticas).
- Outros serviços da VPS publicam portas abertas (8000, 8081, 3001, 8090) sem firewall da Hostinger.
- Backup externo (F7) ainda não existe.

## Desenho antigo (sem uso)

`infra/compose.prod.yaml`, `infra/scripts/deploy.sh`, `infra/scripts/harden-vps.sh` e o workflow `deploy.yml` descrevem um deploy por SSH com Caddy próprio nas portas 80 e 443. **Não rode o `harden-vps.sh` nesta VPS:** ele bloqueia o login do root, e há outros projetos e o Coolify antigo dependendo desse acesso.

## Ainda não existe

Backup (F7), worker (F2), monitoramento (cortado até 18/11).
