# Runbook: VPS e deploy

**Estado em 05/11/2026: nada disto foi executado.** Os scripts passaram por `bash -n` e `shellcheck`, e o Compose de produção por `docker compose config`, mas ainda não existe VPS. O primeiro deploy de verdade vai provavelmente achar problemas; corrija aqui o que achar.

## O que você precisa providenciar

1. **VPS** Ubuntu 22.04 ou 24.04, 2 vCPU e 8 GB (KVM 2 da Hostinger).
2. **Domínio** com um registro `A` apontando para o IP da VPS. Sem isso o Caddy não consegue o certificado HTTPS.
3. **Chave SSH de deploy**, só para este uso: `ssh-keygen -t ed25519 -f h2d-deploy -C deploy`.
4. **Token do GHCR na VPS**, com permissão só de leitura de pacotes (`read:packages`), porque as imagens são privadas.

## 1. Preparar a VPS (uma vez)

Copie [`infra/scripts/harden-vps.sh`](../infra/scripts/harden-vps.sh) para a VPS e rode como root, com a chave **pública**:

```bash
DEPLOY_PUBKEY="$(cat h2d-deploy.pub)" bash harden-vps.sh
```

Antes de fechar a sessão, abra outro terminal e confirme que `ssh -i h2d-deploy deploy@<ip>` entra sem senha. O script desliga o login por senha e o login do root.

## 2. Configurar o servidor

Como usuário `deploy`:

```bash
echo "<token-read-packages>" | docker login ghcr.io -u <seu-usuario-github> --password-stdin
cp /opt/h2d/infra/.env.production.example /opt/h2d/.env   # depois do primeiro envio da infra
```

Edite `/opt/h2d/.env` trocando **todos** os valores. Guarde uma cópia no gerenciador de senhas: sem ela o banco não é recuperável.

## 3. Segredos e variáveis no GitHub

Em Settings → Secrets and variables → Actions:

| Nome | Tipo | Valor |
| --- | --- | --- |
| `VPS_HOST` | segredo | IP ou nome da VPS |
| `VPS_SSH_KEY` | segredo | chave **privada** de deploy |
| `VPS_KNOWN_HOSTS` | segredo | saída de `ssh-keyscan -t ed25519 <ip>`, conferida com a impressão digital do painel da Hostinger |
| `DEPLOY_ENABLED` | variável | `true` (só depois de tudo acima) |

**Aprovação do deploy.** O ambiente `production` existe, mas o GitHub recusou exigir revisor (testado em 05/11/2026: "billing plan does not support the required reviewers protection rule"). Por isso o deploy só roda quando alguém dispara o workflow à mão, e quem tem permissão de escrita no repositório consegue fazê-lo. Se o repositório virar público ou ganhar plano pago, ative o revisor no ambiente.

## 4. Primeiro deploy

Rode o workflow **Deploy** manualmente (Actions → Deploy → Run workflow; todo deploy é assim). Ele publica as imagens, copia `infra/` para `/opt/h2d/infra` e roda [`deploy.sh`](../infra/scripts/deploy.sh), que baixa as imagens, aplica as migrações, sobe tudo e confere `/api/ready` pelo próprio domínio. O primeiro certificado pode levar um ou dois minutos.

Criar o primeiro administrador, sem dados de demonstração:

```bash
cd /opt/h2d && IMAGE_TAG=$(cat .deployed-tag) docker compose --env-file .env -f infra/compose.prod.yaml run --rm \
  -e ADMIN_EMAIL=voce@empresa.com -e ADMIN_NAME="Seu Nome" -e ADMIN_PASSWORD='uma-senha-longa' \
  api python -m h2d.create_admin
```

Para uma demonstração com dados fictícios, use `ALLOW_DEMO_SEED=true` e `SEED_PASSWORD` no `.env` e rode `python -m h2d.seed` do mesmo modo. **Não use com dados reais:** todos os usuários do seed compartilham a mesma senha.

## 5. Rollback

O `deploy.sh` volta sozinho para a versão anterior se `/api/ready` não responder. Para voltar à mão, rode o workflow de novo com um commit anterior, ou na VPS:

```bash
cd /opt/h2d && ./infra/scripts/deploy.sh <tag-anterior>
```

**O rollback não desfaz migrações.** Toda migração precisa funcionar também com o código da versão anterior: primeiro adicione, depois use, só então remova.

## Checklist dos critérios de saída da F1

- [ ] Login do seed funciona em `https://<domínio>`
- [ ] Merge na `main` chega à VPS com `/api/ready` verde
- [ ] Varredura de portas de fora da VPS só mostra 22, 80 e 443 (`nmap -Pn <ip>`)
- [ ] `ssh root@<ip>` e login por senha são recusados

## Ainda não existe

Backup (F7), n8n (F4), worker (F2), monitoramento (cortado até 18/11).
