#!/usr/bin/env bash
# Prepara um servidor Ubuntu novo para rodar o leadpipe.
# Rode como root, logo depois de criar a máquina:
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/pato15z/claude-1/claude/tender-fermi-1albbv/deploy/setup-vps.sh)
#
# O que ele faz: instala o Docker, baixa o código em /opt/leadpipe, cria o .env
# e agenda o backup diário. Não sobe nada ainda — você preenche o .env primeiro.
set -euo pipefail

REPO="https://github.com/pato15z/claude-1.git"
BRANCH="claude/tender-fermi-1albbv"
DIR="/opt/leadpipe"

say(){ printf '\n\033[1;35m==> %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "rode como root (sudo -i)"; exit 1; }

say "pacotes básicos"
apt-get update -qq
# cron não vem em toda imagem mínima do Ubuntu, e sem ele o backup diário
# seria agendado silenciosamente para nunca rodar.
apt-get install -y -qq ca-certificates curl git ufw cron openssl
systemctl enable --now cron >/dev/null 2>&1 || true

say "memória de reserva (swap)"
# Num servidor de 1 ou 2 GB, tanto a instalação do Chromium quanto as abas que
# ele abre depois estouram a RAM e o processo morre sem explicação. 2 GB de swap
# no disco custam nada e transformam "travou" em "ficou mais lento".
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile >/dev/null
  swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  # Só usa o disco quando a RAM está mesmo no fim.
  sysctl -w vm.swappiness=10 >/dev/null
  grep -q '^vm.swappiness' /etc/sysctl.conf || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi
free -h | head -3 || true

say "docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
docker --version

say "firewall: só SSH entra"
# O app não precisa de porta aberta — o túnel sai de dentro para a Cloudflare.
ufw allow OpenSSH >/dev/null
ufw --force enable >/dev/null
ufw status | head -5 || true

say "código em $DIR"
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin "$BRANCH" --quiet
  git -C "$DIR" checkout -q "$BRANCH"
  git -C "$DIR" reset --hard "origin/$BRANCH" --quiet
else
  git clone --branch "$BRANCH" --depth 1 "$REPO" "$DIR" --quiet
fi
mkdir -p "$DIR/data"

say ".env"
if [ ! -f "$DIR/deploy/.env" ]; then
  cp "$DIR/deploy/.env.example" "$DIR/deploy/.env"
  # Já deixa uma senha forte no lugar, para nunca existir uma janela sem senha.
  TOK="$(openssl rand -hex 24)"
  sed -i "s|^LEADPIPE_UI_TOKEN=.*|LEADPIPE_UI_TOKEN=$TOK|" "$DIR/deploy/.env"
  chmod 600 "$DIR/deploy/.env"
  echo "criado $DIR/deploy/.env com senha gerada"
else
  echo "$DIR/deploy/.env já existe, mantido"
fi

say "backup diário às 4h"
chmod +x "$DIR/deploy/backup.sh"
CRON="0 4 * * * $DIR/deploy/backup.sh >> /var/log/leadpipe-backup.log 2>&1"
TMP="$(mktemp)"
( crontab -l 2>/dev/null || true ) | grep -v 'leadpipe/deploy/backup.sh' > "$TMP" || true
echo "$CRON" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"
crontab -l 2>/dev/null | tail -1 || true

cat <<EOF

PRONTO ATÉ AQUI. Faltam três coisas suas:

  1. Cole o token do túnel no .env:
       nano $DIR/deploy/.env        (campo CLOUDFLARE_TUNNEL_TOKEN)

  2. Copie a pasta data/ do seu PC (banco + sites + imagens) para:
       $DIR/data/

  3. Suba:
       cd $DIR/deploy && docker compose up -d --build

Ver se subiu:   cd $DIR/deploy && docker compose logs -f app
Contar leads:   cd $DIR/deploy && docker compose exec app leadpipe db sql "SELECT COUNT(*) FROM leads"
EOF
