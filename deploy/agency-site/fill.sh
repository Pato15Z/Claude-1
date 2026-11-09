#!/usr/bin/env bash
# Preenche as tres paginas com os seus dados e gera a pasta pronta para publicar.
#   bash deploy/agency-site/fill.sh "Pato Web Studio" contato@patoweb.com "+1 614 555 0100" 12.345.678/0001-90
# Saida: deploy/agency-site/out/  (suba essa pasta no Cloudflare Pages)
set -euo pipefail
[ $# -eq 4 ] || { echo 'uso: fill.sh "EMPRESA" email "+1 telefone" CNPJ'; exit 1; }
cd "$(dirname "$0")"
rm -rf out && mkdir out && cp site.css out/
for f in index.html privacy.html terms.html; do
  python3 - "$f" "$1" "$2" "$3" "$4" "$(date +'%B %-d, %Y')" > "out/$f" <<'PY'
import sys, html
f, biz, email, phone, cnpj, date = sys.argv[1:]
s = open(f, encoding="utf-8").read()
for k, v in {"BUSINESS": biz, "EMAIL": email, "PHONE": phone, "CNPJ": cnpj, "DATE": date}.items():
    s = s.replace("{{%s}}" % k, html.escape(v))
sys.stdout.write(s)
PY
done
if grep -l '{{' out/*.html; then echo "ainda ha campo sem preencher"; exit 1; fi
echo "pronto: $(pwd)/out"
