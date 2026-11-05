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

## Rollback

O rollback não desfaz migrações. Toda migração precisa funcionar também com o código da versão anterior: primeiro adicione, depois use, só então remova. Para voltar o código, reverta o commit na `main` e faça **Pull and redeploy**.

## n8n

Sobe junto, com banco próprio (`n8n`) e sem endereço público (decisão D4). Se for preciso abrir o editor, o Caddy da VPS precisa de um bloco para `N8N_DOMAIN` apontando para `h2d-n8n:5678`, de preferência com senha ou restrito a um IP. Quem abrir primeiro vira dono: crie o usuário na hora. Guarde `N8N_ENCRYPTION_KEY` fora da VPS.

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
