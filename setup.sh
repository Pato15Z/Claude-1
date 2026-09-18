#!/usr/bin/env bash
# Instalação em um comando (Mac/Linux). Windows: setup.ps1
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e ".[dev]"
playwright install chromium
lp db init
lp doctor
echo
echo "Pronto. Sempre que abrir um terminal novo: source .venv/bin/activate"
echo "Teste pequeno: lp source maps --vertical \"roof cleaning\" --state OH --city Columbus --max-results 30 --debug"
