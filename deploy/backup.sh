#!/usr/bin/env bash
# Backup diário do banco, com rotação de 14 dias.
#
# `lp db backup` faz wal_checkpoint antes de copiar, então o arquivo gerado é
# consistente mesmo com o app rodando — copiar o .db na mão, sem isso, pode
# levar um banco pela metade.
set -euo pipefail
cd "$(dirname "$0")"

docker compose exec -T app leadpipe db backup

BACKUPS="$(cd .. && pwd)/data/backups"
find "$BACKUPS" -name 'leadpipe-*.db' -mtime +14 -delete 2>/dev/null || true
echo "backups em $BACKUPS:"
ls -1t "$BACKUPS" | head -3
