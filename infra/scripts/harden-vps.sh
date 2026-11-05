#!/usr/bin/env bash
# Prepara uma VPS Ubuntu nova (22.04 ou 24.04). Rode como root, UMA vez, com a chave pública
# do usuário de deploy: DEPLOY_PUBKEY="ssh-ed25519 AAAA... deploy" bash harden-vps.sh
#
# Faz: atualizações, usuário "deploy", SSH só por chave sem root, firewall (22, 80, 443),
# fail2ban, atualizações de segurança automáticas, Docker e a pasta /opt/h2d.
# Pode ser executado de novo sem estragar nada.
#
# ANTES de fechar a sessão atual, abra outra e confirme que "ssh deploy@<ip>" funciona.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Rode como root." >&2; exit 1; }
: "${DEPLOY_PUBKEY:?defina DEPLOY_PUBKEY com a chave pública (ssh-ed25519 ...)}"
case "$DEPLOY_PUBKEY" in
  ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*) ;;
  *) echo "DEPLOY_PUBKEY não parece uma chave pública SSH." >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive

echo "==> Pacotes e atualizações"
apt-get update -y
apt-get upgrade -y
apt-get install -y ufw fail2ban unattended-upgrades curl ca-certificates

echo "==> Atualizações de segurança automáticas"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

echo "==> Docker"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck disable=SC1091
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

echo "==> Usuário deploy"
id deploy >/dev/null 2>&1 || adduser --disabled-password --gecos "" deploy
usermod -aG docker deploy   # quem está no grupo docker equivale a root: guarde bem a chave
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
echo "$DEPLOY_PUBKEY" > /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
install -d -m 750 -o deploy -g deploy /opt/h2d

echo "==> SSH: só chave, sem root"
cat > /etc/ssh/sshd_config.d/99-h2d.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers deploy
MaxAuthTries 3
EOF
sshd -t   # se a configuração estiver errada, o script para aqui, antes de recarregar
systemctl reload ssh 2>/dev/null || systemctl reload sshd

echo "==> Firewall"
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

echo "==> fail2ban"
cat > /etc/fail2ban/jail.d/h2d.local <<'EOF'
[sshd]
enabled = true
maxretry = 4
bantime = 1h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban

cat <<'EOF'

Pronto. Agora, SEM fechar esta sessão:
  1. Em outro terminal: ssh deploy@<ip-da-vps>   (precisa entrar sem pedir senha)
  2. Só depois, saia daqui.

Atenção: o Docker publica portas direto no iptables e ignora o ufw. Por isso o banco não tem
"ports" no compose de produção. Nunca publique outra porta sem revisar.
EOF
