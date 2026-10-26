#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null || { echo 'Установите Python 3.11+ и повторите.'; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3,11), "Нужен Python 3.11+"'
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -f config/workspace.local.json ]]; then
  cp config/workspace.example.json config/workspace.local.json
fi
mkdir -p .local/chrome-profile styles/work/input styles/work/product_runs styles/work/batch_state styles/work/reports retention/receipts retention/final-verifications retention/cleanup-logs
echo 'Окружение установлено. Это ещё не проверка CMS. Далее: docs/MAC-SETUP.md.'
